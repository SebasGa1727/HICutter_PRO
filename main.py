import sys
import os
import ctypes
import multiprocessing
from PyQt6 import QtWidgets, QtGui, QtCore
from utils.logger import setup_logger

logger = setup_logger(__name__)

# @ Created by SGV.dev

# Le decimos a YOLO que estamos en producción y tiene prohibido auto-actualizarse o descargar cosas.
os.environ["YOLO_AUTOUPDATE"] = "False"
os.environ["YOLO_VERBOSE"] = "False"

def resource_path(relative_path: str) -> str:
    """Calcula la ruta absoluta de forma segura para PyInstaller (Bootstrapper version)."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

def setup_windows_appid():
    """Fuerza a Windows a agrupar la app bajo su propio ícono en la barra de tareas."""
    if sys.platform == 'win32':
        try:
            myappid = 'sgv.hicutter.pro.1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logger.warning(f"No se pudo establecer el AppUserModelID: {e}")


class InitWorker(QtCore.QThread):
    """
    Obrero Enterprise: Precarga en la memoria RAM los binarios pesados 
    sin bloquear el renderizado del Splash Screen.
    """
    progress = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def run(self):
        # 1. Librerías matemáticas y de visión (Escritas en C/C++)
        self.progress.emit("Cargando motores de visión (OpenCV y Numpy)...")
        import cv2
        import numpy
        
        # 2. Motor de IA (El cuello de botella más grande de la app)
        self.progress.emit("Inicializando motor de Inteligencia Artificial y tensores...")
        import torch
        try:
            import ultralytics
        except ImportError:
            pass # Previene crasheos si el entorno virtual no tiene ultralytics al momento de pruebas
        
        # 3. Módulos internos pesados
        self.progress.emit("Cargando módulos de procesamiento HICutter...")
        import core.processor
        import core.batch_engine
        import core.ai_batch_mode
        
        self.progress.emit("Preparando entorno gráfico...")
        self.finished.emit()


def main() -> None:
    setup_windows_appid()

    app = QtWidgets.QApplication(sys.argv)
    
    icon_path = resource_path("resources/hicutter_logo_black.png")
    app_icon = QtGui.QIcon(icon_path)
    app.setWindowIcon(app_icon)

    # MOSTRAR SPLASH SCREEN INMEDIATAMENTE
    splash_path = resource_path("resources/hicutter_full_black.png")
    splash_pix = QtGui.QPixmap(splash_path)
    splash_pix = splash_pix.scaled(600, 400, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
    splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    
    # Forzamos a Qt a renderizar la ventana vacía en este instante
    app.processEvents() 

    def update_splash(text):
        splash.showMessage(text, QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignCenter, QtCore.Qt.GlobalColor.white)

    def on_init_finished():
        """
        Callback ejecutado cuando el worker termina.
        Como el worker ya precargó OpenCV, Torch y el core en la caché de Python, 
        esta importación tomará milisegundos y evitará el congelamiento.
        """
        update_splash("Montando interfaz principal...")
        app.processEvents()

        # Importaciones diferidas de la UI
        import app_window
        from ui.components.neon_widgets import NeonProxyStyle
        from utils.asset_manager import assets
        
        # Aplicar estilos globales
        base_style = QtWidgets.QStyleFactory.create("Fusion")
        app.setStyle(NeonProxyStyle(base_style))
        try:
            qss_path = resource_path("resources/theme.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                qss_content = f.read()

            # Interceptamos el CSS y reescribimos las rutas al vuelo.
            # Convertimos las barras a diagonales (/) porque el motor CSS de Qt las exige.
            abs_res_path = resource_path("resources").replace("\\", "/")
            
            # Reemplazamos la ruta relativa por la absoluta de PyInstaller
            qss_content = qss_content.replace("url(resources/", f"url({abs_res_path}/")
            
            app.setStyleSheet(qss_content)
        except FileNotFoundError:
            pass
        assets.init_graphic_resources()

        # Instanciar orquestador en el Hilo Principal (Estricto en PyQt6)
        app._main_window = app_window.MainWindow()
        app._main_window.resize(1000, 700)
        app._main_window.showMaximized()
        
        splash.finish(app._main_window)

    # Iniciar Worker de carga real
    worker = InitWorker()
    worker.progress.connect(update_splash)
    worker.finished.connect(on_init_finished)
    
    # Prevenimos que el recolector de basura (Garbage Collector) elimine el worker
    app._init_worker = worker 
    worker.start()

    sys.exit(app.exec())

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()