import sys
import cv2
import numpy as np
import os
import gc
import time
from enum import IntEnum
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import QThreadPool
from core.batch_engine import BatchManager, BatchWorker, PreloadWorker
from core.processor import process_perspective_crop, rotate_image
from core.converter_engine import ProxyManager, DirectConvertManager
from core.output_fmt import export_image
from core.AI_exporter import split_dataset_train_val
from core.ai_batch_mode import AIBatchWorker, AIFastCropWorker
from image_canvas import ImageCanvas
from ui.views.landing_view import LandingView
from ui.views.converter_setup_view import DirectConvertView
from ui.views.pdf_converter_view import PDFConverterView
from ui.views.ai_batch_view import AIBatchProcessView
from ui.dialogs.ai_resume_dialog import AIResumeDialog
from ui.components.editor_toolbar import EditorToolbar
from ui.components.neon_widgets import NeonProxyStyle
from utils.logger import setup_logger
from utils.asset_manager import assets

# @ Created by SGV.dev

logger = setup_logger(__name__)

class ViewIndex(IntEnum):
    """
    Enumerador para el enrutamiento del QStackedWidget.
    Garantiza que no usemos 'Magic Numbers' en el código.
    """
    LANDING = 0
    CONVERTER = 1
    CANVAS = 2
    PDF_CREATOR = 3
    MODO_IA = 4 

class MainWindow(QtWidgets.QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle('HICutter')

		self.stack = QtWidgets.QStackedWidget()
		self.landing = LandingView()
		self.canvas = ImageCanvas()
		self.converter = DirectConvertView()
		self.pdf = PDFConverterView()
		self.ai_view = AIBatchProcessView()
		self.stack.insertWidget(ViewIndex.LANDING, self.landing)
		self.stack.insertWidget(ViewIndex.CONVERTER, self.converter)
		self.stack.insertWidget(ViewIndex.CANVAS, self.canvas)
		self.stack.insertWidget(ViewIndex.PDF_CREATOR, self.pdf)
		self.stack.insertWidget(ViewIndex.MODO_IA, self.ai_view)
		self.setCentralWidget(self.stack)
		self.current_image_path: str | None = None

		# Inicializamos el enrutador central
		self._setup_routing()

		# Motor de proxies
		self.proxy_manager = ProxyManager()
		self.proxy_manager.progress.connect(self._on_proxy_progress)
		self.proxy_manager.finished.connect(self._on_proxy_finished)
		self.proxy_manager.error.connect(self._on_proxy_error)
		self.proxy_manager.system_alert.connect(self._show_os_notification)
		self.proxy_manager.process_resume.connect(self._quit_os_notification)
		self._out_of_ram_warning = None
		self.proxy_wait_dialog = None

		# Motor de Exportación Directa (Convertidor)
		self.direct_convert_manager = DirectConvertManager()
		self.direct_convert_manager.global_progress.connect(self._on_proxy_progress) # Reciclamos tu UI de progreso
		self.direct_convert_manager.finished.connect(self._on_direct_convert_finished)
		self.direct_convert_manager.system_alert.connect(self._show_os_notification)
		self.direct_convert_manager.process_resume.connect(self._quit_os_notification)

		#Procesamiento por lote implementado desde Batch_engine
		self.is_batch_mode: bool = False
		self.batch_manager = BatchManager()
		# Banderas de modo lote con IA
		self._current_workflow = None  # Puede ser "manual_batch" o "ai_batch"
		self.is_ai_mode = False
		self.is_ai_paused = False
		self.is_ai_cancelled = False
		self.ai_start_time = 0.0
		#Gestores de hilos para precesamiento asincrono y lectura de imagen asincrona en 2 vias
		self.cpu_pool = QThreadPool()
		# Pool para lectura de disco, limitado a solo 1 nucleo
		self.io_pool = QThreadPool()
		self.io_pool.setMaxThreadCount(1)
		#Buffer de cache - "Look ahead" para la lectura de la imagen futura
		self.next_image_buffer: np.ndarray | None = None
		self.next_image_path_buffer: str | None = None
		self.next_image_error: tuple[str, str] | None = None
		#Banderas de control de estado asincrono
		self._is_preloading: bool = False
		self._waiting_for_preload: bool = False
		self.batch_manager.batch_finished.connect(self._on_batch_finished)
		self.parent_folder_name: str = ""

		# Toolbar implementado desde "editor_toolbar.py"
		self.toolbar = EditorToolbar(self)
		self.addToolBar(self.toolbar)
		
		#Conectamos las "señales" enviadas desde "editor_toolbar.py"
		self.toolbar.sig_reset_requested.connect(self.canvas.reset_points)
		self.toolbar.sig_rotate_right_requested.connect(lambda: self._apply_rotation("derecha"))
		self.toolbar.sig_rotate_left_requested.connect(lambda: self._apply_rotation("izquierda"))
		self.toolbar.sig_rotate_180_requested.connect(lambda: self._apply_rotation("180"))
		self.toolbar.sig_cancel_requested.connect(self.cancel_operation)

		# Atajos globales
		self.KEY_ENTER: list =["Return", "Enter"] 
		self.shortcut_return = QtGui.QShortcut(QtGui.QKeySequence(self.KEY_ENTER[0]), self)
		self.shortcut_return.activated.connect(self._on_enter_key)
		self.shortcut_enter = QtGui.QShortcut(QtGui.QKeySequence(self.KEY_ENTER[1]), self)
		self.shortcut_enter.activated.connect(self._on_enter_key)

		#Señales del canvas 
		self.canvas.sig_save_requested.connect(self._on_enter_key)

		# Mostrar la LandingView inicialmente
		self._navigate_to(ViewIndex.LANDING)
		self.update_toolbar_state(False)

		# Metodos de enrutado (navegacion entre las vistas)
	def _setup_routing(self) -> None:
		"""
        Actúa como el controlador central. Desacopla las vistas conectando sus señales a la lógica de navegación.
        """
        # --- Desde la Landing View ---
		self.landing.requestConverter.connect(lambda: self._navigate_to(ViewIndex.CONVERTER))
		self.landing.requestCreatePDF.connect(lambda: self._navigate_to(ViewIndex.PDF_CREATOR))
		self.landing.requestLoadImage.connect(self._handle_request_load_image)
		self.landing.requestLoadBatch.connect(self._start_batch_workflow)
		self.landing.requestLoadAI.connect(self._start_ai_workflow)
		self.converter.request_convert.connect(self._start_direct_conversion)

        # --- Desde las vistas de Trabajo (Atrás / Cancelar) ---
		self.converter.request_cancel.connect(self._navigate_home)
		self.pdf.request_cancel.connect(self._navigate_home)
		
		# --- Desde la vista IA ---
		self.ai_view.request_cancel.connect(lambda: self.cancel_operation(prompt_user=True))
		self.ai_view.request_pause_resume.connect(self._on_ai_pause_toggled)

		# Actualizar estado del toolbar de forma inteligente
		self.stack.currentChanged.connect(self._on_view_changed)

	def _navigate_to(self, view_index: ViewIndex) -> None:
		"""Cambia la vista activa y prepara el entorno si es necesario."""
		self.stack.setCurrentIndex(view_index)

	def _navigate_home(self) -> None:
		"""
		Lógica inteligente de retorno (Mejora de UX).
		Si estamos procesando un lote, pedimos confirmación. Si la vista está "limpia", regresa sin molestar.
		"""
		if self.is_batch_mode or getattr(self, "_is_preloading", False) or self.is_ai_mode:
			# Si hay trabajo crítico, usamos la función pesada original
			self.cancel_operation(prompt_user=True)
		else:
			# Si es solo navegación de menús, regresamos transparente y limpiamos
			self.current_image_path = None
			self.canvas.unload_image()
			self._navigate_to(ViewIndex.LANDING)

	def _on_view_changed(self, idx: int) -> None:
		"""Gestiona qué herramientas están disponibles según la vista activa."""
		# El editor toolbar solo debe estar activo en el Canvas 
		is_canvas_active = (idx == ViewIndex.CANVAS)
		self.update_toolbar_state(is_canvas_active)

	# metodos del convertidor
	def _start_direct_conversion(self, payload: dict):
		"""Lanza el proceso de exportación final del Convertidor."""
		# Reciclamos tu diálogo de espera que usas en los proxies
		self.proxy_wait_dialog = QtWidgets.QProgressDialog("Inicializando exportación...", "Cancelar", 0, len(payload["manifest"]), self)
		self.proxy_wait_dialog.setWindowTitle("Convirtiendo Acervo")
		self.proxy_wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self.proxy_wait_dialog.setAutoClose(False)
		self.proxy_wait_dialog.setAutoReset(False)
		self.proxy_wait_dialog.canceled.connect(self.direct_convert_manager.cancel)
		self.proxy_wait_dialog.show()

		# Arrancar motor
		self.direct_convert_manager.process_manifest(payload["output_dir"], payload["manifest"])

	def _on_direct_convert_finished(self, successes: int, errors: int):
		"""Cierra el diálogo y purga la memoria del Registry."""
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None

		# Importante: Limpiamos la RAM de los filtros guardados
		from core.filter_registry import FilterRegistry
		FilterRegistry.clear_memory()

		QtWidgets.QMessageBox.information(
			self, "Conversión Terminada",
			f"Proceso finalizado.\n\n✔️ Exportados: {successes}\n⚠️ Errores: {errors}"
		)
		# Devuelve al usuario a una interfaz limpia
		self._navigate_home()

	#Metodos del proxy
	def _on_proxy_progress(self, actuales: int, totales: int, mensaje: str):
		'''Recibe actualizaciones del obrero de la bobeda'''
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			self.proxy_wait_dialog.setMaximum(totales)
			self.proxy_wait_dialog.setValue(actuales)
			self.proxy_wait_dialog.setLabelText(mensaje)

	def _on_proxy_finished(self, final_list: list[str]):
		'''Se ejecuta cuando la bobeda termino de procesar todas las imagenes'''
		#Quitamos la pantalla de carga
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			try:
				self.proxy_wait_dialog.canceled.disconnect()
			except Exception:
				pass
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		
		# Limpiamos la lista de nulos
		clean_list = [f for f in final_list if f]
		if not clean_list:
			self.is_batch_mode = False
			QtWidgets.QMessageBox.warning(self, "Aviso", "No se encontraron imágenes válidas en la carpeta.")
			return

		# Switch de enrutamiento basado en _current_workflow
		if self._current_workflow == "ai_batch":
			self._start_ai_processing(clean_list)
		else:
			if self.batch_manager.set_files(clean_list):
				self.is_batch_mode = True
				logger.info(f"Lote iniciado: {len(self.batch_manager.image_files)} fotos en cola")
				self._load_next_batch_image(force_sync= True)

	def _on_proxy_error(self, err_msg: str):
		'''Error de procesamiento de proxys'''
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			try:
				self.proxy_wait_dialog.canceled.disconnect()
			except Exception:
				pass
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		QtWidgets.QMessageBox.critical(self, "Error de Carpeta", err_msg)	

	def _cancel_proxies(self):
		'''Proceso si el usuario cancela mientras se crea el proxy'''
		self.proxy_manager.cancel()
		self.cancel_operation(prompt_user=False)

		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		self.is_batch_mode = False
		logger.info("El usuario canceló la generación de proxies.")

	def _show_os_notification(self, msg: str) -> None:
		'''Metodo para enviar notificacion de sistema al usuario por falta de RAM'''
		# Seguro anti SPAM
		if getattr(self, "_is_showing_alert", False):
			return
		
		self._is_showing_alert = True

		QtWidgets.QApplication.alert(self)

		if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
			tray_icon = QtWidgets.QSystemTrayIcon(self.windowIcon(), self)
			tray_icon.show()
			tray_icon.showMessage("HICutter - Atención Requerida", msg, QtWidgets.QSystemTrayIcon.MessageIcon.Warning, 10000) # 10 segundos

		self._out_of_ram_warning = QtWidgets.QProgressDialog(msg, None, 0, 0, self)
		self._out_of_ram_warning.setWindowTitle("⚠️ PROCESO PAUSADO ⚠️")
		self._out_of_ram_warning.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self._out_of_ram_warning.setCancelButton(None)
		current_flags = self._out_of_ram_warning.windowFlags()
		self._out_of_ram_warning.setWindowFlags(current_flags & ~QtCore.Qt.WindowType.WindowCloseButtonHint)
		self._out_of_ram_warning.show()

	def _quit_os_notification(self, state: bool) -> None:
		'''Metodo para eliminar la notificacion del usuario por falta de ram'''
		if getattr(self, "_out_of_ram_warning", None)is not None and state:
			self._out_of_ram_warning.hide()
			self._out_of_ram_warning.deleteLater()
			self._out_of_ram_warning = None
			self._is_showing_alert = False

	# Metodos para cargar la imagen y flujo de trabajo
	def load_image(self, path: str | None = None) -> None:
		# Si se proporciona `path`, úsalo; si no, abrir dialogo de archivo
		if path is None:
			fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Abrir imagen', 'input', 'Images (*.png *.jpg *.jpeg *.bmp *.cr2 *.tif *.tiff)')
			if not fname:
				return
		else:
			fname = path
		img = cv2.imread(fname)
		if img is None:
			QtWidgets.QMessageBox.warning(self, 'Error', 'No se pudo cargar la imagen')
			return
		self.current_image_path = fname

		# Colocamos la informacion del HUD para el modo individual
		nombre_archivo = os.path.basename(fname)
		self.canvas.set_hud_info(nombre_archivo, "Procesamiento individual")

		self.canvas.load_image(cv_image=img)
		# Cambiar a la vista del editor
		self._navigate_to(ViewIndex.CANVAS)
		
	def _on_enter_key(self) -> None:
		# Ejecuta save_points si hay 4 puntos seleccionados
		pts = self.canvas.get_points()
		if pts.shape[0] == 4:
			if self.is_batch_mode:
				self._process_batch_image() #<- Ejecutamos guardado de forma asincrona (lotes)
			else:
				self.save_points()#<- Ejecutamos guardado de forma sincrona (1 imagen)

	def _handle_request_load_image(self, *args) -> None:
		# Wrapper that accepts optional path from LandingView signal
		path = args[0] if args else None
		self.load_image(path)

	def _apply_rotation(self, direction_rotate: str) -> None:
		"""Se aplica la rotacion (via processor.rotate_image) y recarga la imagen via canvas"""
		if self.canvas.cv_image is None:
			return
		rotated = rotate_image(self.canvas.cv_image, direction_rotate)
		# reload the rotated image into the canvas
		self.canvas.load_image(cv_image=rotated)

	def update_toolbar_state(self, editor_active: bool) -> None:
		'''Activa/desactiva las heramientas si hay o no imagen cargada'''
		try:
			#Apagamos o encendemos la toolbar
			self.toolbar.set_editor_active(editor_active)
		except Exception:
			logger.error("Error al activar/desactivar la toolbar", exc_info=True)
		
		try:
			#Apagamos o encendemos los shortcuts
			self.shortcut_enter.setEnabled(editor_active)
			self.shortcut_return.setEnabled(editor_active)
		except Exception:
			logger.warning("LA funcionalidad de 'Shortcuts' no fue activada/desactivada correctamente", exc_info=True)

	# Metodos para trabajo asincrono del modo lote
	def _start_batch_workflow(self):
		self._initialize_workflow("manual_batch")

	def _start_ai_workflow(self):
		self._initialize_workflow("ai_batch")

	def _initialize_workflow(self, mode: str):
		"""Unifica el diálogo de Setup y el Proxy para cualquier modo de lote"""
		self._current_workflow = mode
		from ui.dialogs.batch_setup_dialog import BatchSetupDialog
		from utils.batch_config import config_manager
		
		dialog = BatchSetupDialog(self)

		if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
			carpeta_entrada = config_manager.get("save_config", "last_input_route")
			self.parent_folder_name = os.path.basename(os.path.normpath(carpeta_entrada))

			self.proxy_wait_dialog = QtWidgets.QProgressDialog("Analizando bóveda de archivos...", "Cancelar", 0, 100, self)
			self.proxy_wait_dialog.setWindowTitle("Escaneando Carpeta")
			self.proxy_wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
			self.proxy_wait_dialog.setAutoClose(False)
			self.proxy_wait_dialog.setAutoReset(False)
			self.proxy_wait_dialog.canceled.connect(self._cancel_proxies)
			self.proxy_wait_dialog.show()

			# Manda a llamar al generador de proxyes
			self.proxy_manager.process_directory(carpeta_entrada)

	# Motor de IA
	def _start_ai_processing(self, image_list: list[str]):
		"""Instancia la vista y el Worker de IA tras el filtro del ProxyManager"""
		self.is_ai_mode = True
		self.is_ai_paused = False
		self.is_ai_cancelled = False
		self.ai_start_time = time.perf_counter()
		
		# Resetear la UI de IA
		self.ai_view.update_progress(0, len(image_list))
		self.ai_view.update_counters(0, 0)
		self.ai_view.log_terminal.clear()
		self.ai_view.log_message("Inicializando procesamiento de IA")
		
		self._navigate_to(ViewIndex.MODO_IA)
		
		# Instanciar el Worker inyectando las lambdas de evaluación (Seguridad en Memoria)
		ai_worker = AIBatchWorker(
			image_list=image_list,
			check_cancel_func=lambda: self.is_ai_cancelled,
			check_pause_func=lambda: self.is_ai_paused
		)
		
		# Conectar señales del hilo a los métodos de actualización
		ai_worker.signals.progress.connect(self._on_ai_progress)
		ai_worker.signals.log.connect(self.ai_view.log_message)
		ai_worker.signals.finished.connect(self._on_ai_finished)
		ai_worker.signals.error.connect(self._on_ai_error)
		
		# Despachar al Pool
		self.cpu_pool.start(ai_worker)

	def _on_ai_pause_toggled(self, is_paused: bool):
		"""Recibe el estado desde el toggle de la vista y actualiza la bandera de Main"""
		self.is_ai_paused = is_paused

	def _on_ai_progress(self, current: int, total: int, success: int, review: int, filename: str):
		"""Actualiza HUD y calcula ETA en tiempo real"""
		self.ai_view.update_progress(current, total)
		self.ai_view.update_counters(success, review)
		self.ai_view.update_current_file(filename)
		
		elapsed = time.perf_counter() - self.ai_start_time
		avg_time = elapsed / current if current > 0 else 0
		rem_items = total - current
		eta_secs = avg_time * rem_items
		
		def fmt_time(s):
			if s > 60: return f"{int(s//60)}m {int(s%60)}s"
			return f"{int(s)}s"
			
		self.ai_view.update_times(fmt_time(elapsed), fmt_time(eta_secs))

	def _on_ai_finished(self, success_list: list, review_list: list):
		"""Flujo de Triaje Post-IA con validación humana interactiva."""
		self.is_ai_mode = False
		split_dataset_train_val(porcentaje_train=0.8)
		
		if self.is_ai_cancelled:
			self._cleanup_thumbnails(review_list)
			return
		
		# Caso ideal: Todas pasaron el porcentaje de validacion
		if not review_list:
			QtWidgets.QMessageBox.information(
				self, 
				"Resumen de IA", 
				f"Procesamiento IA Finalizado.\n\n✔️ Éxitos (Guardados): {len(success_list)}\n⚠️ Para revisión: 0"
			)
			self._navigate_to(ViewIndex.LANDING)
			return

		# Levantar el Diálogo de Triaje para las reprobadas
		dialog = AIResumeDialog(review_list, self)
		result = dialog.exec()
		
		if result == QtWidgets.QDialog.DialogCode.Accepted:
			accepted_for_ai, rejected_for_manual = dialog.get_triage_results()
			self._cleanup_thumbnails(review_list) # Limpiar disco de miniaturas
			
			if accepted_for_ai:
				self._run_ai_fast_crop(accepted_for_ai, rejected_for_manual, len(success_list))
			else:
				# Si no aceptó ninguna de la IA, saltamos directo al triaje manual
				self._transition_post_triage(rejected_for_manual, len(success_list))
		else:
			# Si el usuario presiona la "X" o Escape, abortamos y limpiamos
			self._cleanup_thumbnails(review_list)
			self._navigate_to(ViewIndex.LANDING)

	def _cleanup_thumbnails(self, review_list: list):
		"""Utilidad para mantener el disco limpio de los archivos temporales generados por la IA."""
		for item in review_list:
			thumb = item.get("thumb_path")
			if thumb and os.path.exists(thumb):
				try:
					os.remove(thumb)
				except OSError:
					logger.warning(f"No se pudo eliminar el archivo temporal: {thumb}")

	def _run_ai_fast_crop(self, accepted_data: list, rejected_paths: list, previous_success_count: int):
		"""Orquesta el recorte matemático rápido (100ms) en segundo plano para no congelar la UI."""
		self.fast_crop_dialog = QtWidgets.QProgressDialog("Aplicando recortes confirmados...", None, 0, len(accepted_data), self)
		self.fast_crop_dialog.setWindowTitle("Procesando")
		self.fast_crop_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self.fast_crop_dialog.setCancelButton(None)
		self.fast_crop_dialog.show()

		self.fast_worker = AIFastCropWorker(accepted_data)
		# Conectamos el progreso al QProgressDialog
		self.fast_worker.signals.progress.connect(lambda c, t: self.fast_crop_dialog.setValue(c))
		# Inyectamos por lambda las variables de arrastre para no perder los datos del triaje
		self.fast_worker.signals.finished.connect(
			lambda s_list, e_list: self._on_ai_fast_crop_finished(s_list, e_list, rejected_paths, previous_success_count)
		)
		self.cpu_pool.start(self.fast_worker)

	def _on_ai_fast_crop_finished(self, fast_success: list, fast_error: list, rejected_paths: list, previous_success_count: int):
		"""Callback al terminar el worker de recortes rápidos."""
		if hasattr(self, 'fast_crop_dialog') and self.fast_crop_dialog:
			self.fast_crop_dialog.close()

		total_success = previous_success_count + len(fast_success)
		# Si por algún motivo de memoria un fast crop falla, lo enviamos al lote manual por seguridad
		combined_rejected = rejected_paths + fast_error 

		self._transition_post_triage(combined_rejected, total_success)

	def _transition_post_triage(self, rejected_paths: list, total_success: int):
		"""Evalúa si transiciona al modo lote manual en el Canvas o si termina el flujo de IA volviendo a Landing."""
		if not rejected_paths:
			QtWidgets.QMessageBox.information(
				self, 
				"Resumen de IA", 
				f"Procesamiento Finalizado exitosamente.\n\n✔️ Imágenes exportadas: {total_success}"
			)
			self._navigate_to(ViewIndex.LANDING)
			return

		msg = f"Procesamiento Finalizado.\n\n✔️ Imágenes exportadas: {total_success}\n⚠️ Imágenes para recorte manual: {len(rejected_paths)}"
		
		resp = QtWidgets.QMessageBox.question(
			self, "Modo Lote Manual",
			msg + "\n\n¿Deseas procesar las imágenes restantes manualmente ahora mismo?",
			QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
		)

		if resp == QtWidgets.QMessageBox.StandardButton.Yes:
			# Inyectamos los fallos al sistema de lotes
			if self.batch_manager.set_files(rejected_paths):
				self.is_batch_mode = True
				self._load_next_batch_image(force_sync=True)
			else:
				self._navigate_to(ViewIndex.LANDING)
		else:
			self._navigate_to(ViewIndex.LANDING)

	def _on_ai_error(self, err_msg: str):
		self.is_ai_mode = False
		QtWidgets.QMessageBox.critical(self, "Error de Inferencia", err_msg)
		self._navigate_to(ViewIndex.LANDING)

	def _load_next_batch_image(self, force_sync: bool = False):
		"""Orquesta la extracción de imágenes, priorizando la memoria RAM (Buffer)."""
		# CASO A: Primera imagen o lectura forzada (I/O Síncrono)
		if force_sync:
			path = self.batch_manager.get_next_image()
			if not path:
				return
			
			img = cv2.imread(path)
			if img is not None:
				self._render_image_to_canvas(path, img)
				self._trigger_preload()
			else:
				self.batch_manager.record_error(path, "Lectura síncrona fallida.")
				self._load_next_batch_image(force_sync=True)
			return

		# CASO B: El usuario fue más rápido que el disco duro
		if self._is_preloading:
			# Levantamos la bandera de espera. El callback lo procesará en cuanto termine.
			self._waiting_for_preload = True
			QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
			return

		# CASO C: Error en la precarga (Manejo de UX)
		if self.next_image_error is not None:
			err_path, err_msg = self.next_image_error
			self.next_image_error = None # Vaciamos el error
			
			self.batch_manager.record_error(err_path, err_msg)
			
			msg_box = QtWidgets.QMessageBox(self)
			msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
			msg_box.setWindowTitle("Error en el archivo")
			msg_box.setText(f"No se pudo leer la siguiente imagen:\n{err_path}\n\n¿Qué deseas hacer?")
			
			btn_continuar = msg_box.addButton("Continuar con la siguiente", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
			btn_abortar = msg_box.addButton("Abortar Lote", QtWidgets.QMessageBox.ButtonRole.RejectRole)
			msg_box.exec()
			
			if msg_box.clickedButton() == btn_abortar:
				self.cancel_operation(prompt_user=False)
			if msg_box.clickedButton() == btn_continuar:
				# Si decide continuar, forzamos lectura de la siguiente para brincarnos la corrupta
				self._load_next_batch_image(force_sync=True)
			return

		# CASO D: Final del Lote (Buffer vacío y el hilo no está trabajando)
		if self.next_image_buffer is None:
			self._finish_batch_ui()
			return

		# CASO E: Swap de Memoria Instantáneo (Éxito Nominal)
		img, scaled_qimg = self.next_image_buffer
		path = self.next_image_path_buffer
		
		# Propiedad estricta: Limpiamos el buffer para prevenir Memory Leaks
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		
		self._render_image_to_canvas(path, img, scaled_qimg)
		self._trigger_preload()

	def _render_image_to_canvas(self, path: str, img: np.ndarray, scaled_qimg: QtGui.QImage = None):
		"""Inyecta la matriz al canvas y actualiza el HUD"""
		self.current_image_path = path

		nombre_archivo = os.path.basename(path)
		carpeta_padre = os.path.basename(os.path.dirname(path))

		hud_tittle = f"{carpeta_padre} / {nombre_archivo}"
		
		# Calculamos el progreso basado en el archivo actual de la lista
		try:
			indice = self.batch_manager.image_files.index(path)
			progress = f"{indice + 1}/{len(self.batch_manager.image_files)}"
		except ValueError:
			progress = f"?/{len(self.batch_manager.image_files)}"
		
		self.canvas.set_hud_info(hud_tittle, progress)
		self.canvas.load_image(cv_image=img, pre_scaled_qimage=scaled_qimg)
		self._navigate_to(ViewIndex.CANVAS)

	def _trigger_preload(self):
		"""Calcula cuál es la siguiente foto y lanza el hilo de lectura."""
		next_path = self.batch_manager.get_next_image()
		
		if next_path:
			self._is_preloading = True
			preload_worker = PreloadWorker(next_path, self.canvas.size())
			preload_worker.signals.finished.connect(self._on_preload_success)
			preload_worker.signals.error.connect(self._on_preload_error)
			self.io_pool.start(preload_worker)
		else:
			logger.info("No hay más imágenes para precargar.")

	def _on_preload_success(self, img: object, scaled_qimg: object, path: str):
		"""Callback asíncrono. Guarda la matriz en la RAM y gestiona la condición de carrera."""

		self.next_image_buffer = (img, scaled_qimg)
		self.next_image_path_buffer = path
		self.next_image_error = None
		self._is_preloading = False
		
		# Si el usuario estaba esperando, quitamos el reloj de arena y forzamos el cargado
		if self._waiting_for_preload:
			self._waiting_for_preload = False
			QtWidgets.QApplication.restoreOverrideCursor()
			self._load_next_batch_image()

	def _on_preload_error(self, path: str, err_msg: str):
		"""Callback asíncrono. Registra el fallo para ser notificado cuando el usuario llegue a esa foto."""
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		self.next_image_error = (path, err_msg)
		self._is_preloading = False
		
		if self._waiting_for_preload:
			self._waiting_for_preload = False
			QtWidgets.QApplication.restoreOverrideCursor()
			self._load_next_batch_image()

	def _finish_batch_ui(self):
		"""Despliega el diálogo de cierre esperando a que los obreros de la CPU terminen."""
		self.wait_dialog = QtWidgets.QProgressDialog("Guardando las últimas imágenes...", None, 0, 0, self)
		self.wait_dialog.setWindowTitle("Procesando")
		self.wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self.wait_dialog.setCancelButton(None)
		self.wait_dialog.show()

	def _process_batch_image(self):
		'''Procesa el trabajo de guardado de forma asincrona'''
		if self.canvas.cv_image is None or self.current_image_path is None:
			logger.warning("Error de procesamiento de guardado en canvas o image_path", exc_info=True)
			return

		pts = self.canvas.get_points().astype(np.float32)
		file_path = self.current_image_path
		#Creamos al obrero
		worker = BatchWorker(self.canvas.cv_image, pts, file_path, self.parent_folder_name)
		#Conectamos las señales
		worker.signals.finished.connect(self.batch_manager.record_success)
		worker.signals.error.connect(self.batch_manager.record_error)
		#Lo mandamos a un hilo aparte
		self.cpu_pool.start(worker)
		# Descargamos la imagen vieja del canvas. Esto borra la matriz principal 
		# y el pixmap de la interfaz antes de leer la nueva desde el disco.
		self.canvas.unload_image()
		#Cargamos la siguiente imagen
		self._load_next_batch_image()

	def _on_batch_finished(self, success_list: list, error_list: list):
		'''Se ejecuta cuando el ultimo obrero termina de guardar'''
		# Limpiamos el canvas
		self.canvas.set_hud_info("","")
		self.canvas.unload_image()
		self.current_image_path = None
		self.is_batch_mode = False
		
		# Limpieza de bufer post lote
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		self.next_image_error = None
		gc.collect()

		# Ordenar Dataset de Entrenamiento al terminar un lote
		logger.info("Lote finalizado. Ejecutando partición de Dataset IA Train/Val...")
		split_dataset_train_val(porcentaje_train=0.8)

		# Cerramos el diálogo de espera de guardado si sigue abierto
		if hasattr(self, 'wait_dialog') and self.wait_dialog:
			self.wait_dialog.close()
			
		# Notificamos al usuario MOMENTANEA
		# TODO generar un dialogo que le permita al usuario regresar al landing view o reprocesar las imagenes corruptas
		QtWidgets.QMessageBox.information(
			self, 
			"Lote Terminado", 
			f"Procesamiento finalizado.\nÉxitos: {len(success_list)}\nErrores: {len(error_list)}"
		)

		# Regresamos a la vista principal
		self._navigate_to(ViewIndex.LANDING)

	def save_points(self) -> None:
		"""Guarda la imagen procesada preguntando primero el destino.
					(Procesamiento de una sola imagen)"""
		pts = self.canvas.get_points()
		if pts.shape[0] != 4:
			QtWidgets.QMessageBox.warning(self, 'Aviso', 'Faltan puntos (se requieren 4)')
			return

		if self.canvas.cv_image is None:
			return

		# puntos ordenados en coordenadas de la imagen (float32)
		src = pts.astype(np.float32)
		try:
			warped = process_perspective_crop(self.canvas.cv_image, src)
		except ValueError as e:
			QtWidgets.QMessageBox.warning(self, 'Error', str(e) if str(e) else 'Dimensiones inválidas para el recorte')
			return

		# Invocamos el dialogo de exportacion
		from ui.dialogs.individual_export_dialog import IndividualExportDialog

		basename = os.path.basename(self.current_image_path)
		basename_no_extention, _ = os.path.splitext(basename)
		
		dialog = IndividualExportDialog(basename_no_extention, self)
		if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
			export_data = dialog.get_export_data()
			out_dir = export_data["output_dir"]
			filename = export_data["filename"]

			# --- Extraemos los datos técnicos del JSON del usuario ---
			from utils.individual_config import config_manager as ind_config
			fmt_idx = ind_config.get("export_config", "format")
			fmt = "jpg" if fmt_idx == 0 else "png"
			quality = ind_config.get("export_config", "quality")
			dpi = ind_config.get("export_config", "dpi")
			target_size = ind_config.get("export_config", "size")
			size_side_idx = ind_config.get("export_config", "size_side")
			
			# Mapeado de lado
			anchor_map = {0: "longest_edge", 1: "shortest_edge", 2: "square"}
			anchor = anchor_map.get(size_side_idx, "longest_edge")

			try:
				export_image(
					cv_image=warped, 
					out_dir=out_dir, 
					base_filename=filename,
					target_size=target_size,
					anchor=anchor,
					quality=quality,
					dpi=dpi,
					fmt=fmt,
					sufix=""
				)
				
				self.canvas.unload_image()
				self.current_image_path = None
				QtWidgets.QMessageBox.information(self, "Aviso", f"Imagen guardada exitosamente en:\n{out_dir}")
				self._navigate_to(ViewIndex.LANDING)
			except Exception:
				logger.error("Error al exportar imagen individual", exc_info=True)
				QtWidgets.QMessageBox.warning(self, "Error", "No se pudo exportar la imagen (revise logs)")
	
	
	def cancel_operation (self, prompt_user: bool = True) -> None:
		'''Aborto seguro del procesamiento'''
		'''Confirma la operacion de aborto al usuario'''
		if prompt_user:
			answer = QtWidgets.QMessageBox.question(
				self,
				"Confirmar cancelacion",
				"¿Estas seguro de cancelar el proceso actual y regresar a la pagina de inicio?\n" \
				"Nota: En procesamiento por lote, esta accion solo afecta a la imagen actual.\n" \
				"Las imagenes previas no se veran afectadas.",
				QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, 
				QtWidgets.QMessageBox.StandardButton.No #<- Eleccion por defecto en caso de que se presione "enter"
			)
			if answer == QtWidgets.QMessageBox.StandardButton.No:
				return
		#Ejecutamos el codigo para limpiar el lienzo de forma correcta
		try:
			# Borramos la imagen de la memoria del Canvas
			self.canvas.unload_image()
			# Destruimos la referencia a la ruta original
			self.current_image_path = None
			#Desactivamos el modo lote
			self.is_batch_mode = False
			if getattr(self, "is_ai_mode", False): #<- validamos si esta en modo IA
				self.is_ai_cancelled = True
				self.is_ai_paused = False # Forzamos el False para destrabar el "sleep" en caso de estar pausado
				self.is_ai_mode = False
			#Destruimos todo rastro de la memoria en espera
			self.next_image_buffer = None
			self.next_image_path_buffer = None
			self.next_image_error = None
			gc.collect()
			# Cambiamos la vista a la pantalla Landing (índice 0)
			self.stack.setCurrentIndex(0)

			logger.info("Proceso cancelado y memorias liberadas, de vuelta en pagina de inicio")
		except Exception:
			logger.error("Error al critico al intentar cancelar la operacion", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "Error al limpiar la memoria, intente nuevamente")

def main() -> None:
	app = QtWidgets.QApplication(sys.argv)
	base_style = QtWidgets.QStyleFactory.create("Fusion")
	app.setStyle(NeonProxyStyle(base_style))
	try:
		with open("resources/theme.qss", "r", encoding="utf-8") as f:
			app.setStyleSheet(f.read())
	except FileNotFoundError:
		pass
	assets.init_graphic_resources()

	mw = MainWindow()
	mw.resize(1000, 700)
	mw.showMaximized()
	sys.exit(app.exec())

if __name__ == '__main__':
	main()