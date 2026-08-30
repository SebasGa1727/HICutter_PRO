from PyQt6 import QtWidgets, QtCore, QtGui, QtSvg
from utils.logger import setup_logger
from utils.asset_manager import resource_path

logger = setup_logger(__name__)

class HiddenFilesFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filtra archivos y carpetas que empiezan con punto (.)"""
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        file_name = self.sourceModel().fileName(index)
        
        if file_name.startswith('.'):
            return False # Lo oculta visualmente
            
        return super().filterAcceptsRow(source_row, source_parent)
    
class NeonTreeView(QtWidgets.QTreeView):
    """
    QTreeView personalizado que evita que Windows pinte fondos morados 
    en el área de las ramas/sangrías.
    """
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)

    def drawBranches(self, painter, rect, index):
        # ESCUDO: Nunca intentar dibujar un índice que la memoria C++ aún no haya validado.
        # Esto soluciona el 99% de los crasheos en el primer render.
        if not index.isValid():
            return
        try:
            clean_rect = rect.adjusted(0, -1, 0, 1)
            painter.fillRect(clean_rect, QtGui.QColor("#171717")) # <-Si se cambia el color del fondo, se cambia este para la sangria
            
            # 2. Ahora sí, le decimos a Qt: "Dibuja tus flechas encima de mi lienzo limpio".
            super().drawBranches(painter, rect, index)
        except Exception as e:
            logger.error("Error en 'drawBranches'", exc_info=True)
    
class NeonSelectionDelegate(QtWidgets.QStyledItemDelegate):
    """
    Delegado personalizado que secuestra el pintado de la selección 
    para forzar un color Neón y evitar los colores nativos del SO.
    """
    def paint(self, painter, option, index):
        if not index.isValid():
            return
        
        try:
        # Creamos una copia de las opciones de pintado para poder manipularlas
            opt = QtWidgets.QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)

            # Verificamos si el ítem actual está seleccionado
            if opt.state & QtWidgets.QStyle.StateFlag.State_Selected:
                
                # 1. Borramos el estado "Seleccionado" de la memoria de Qt (El truco maestro)
                # Esto evita que Qt intente pintar su fondo morado por encima y le quita el foco.
                opt.state &= ~QtWidgets.QStyle.StateFlag.State_Selected
                opt.state &= ~QtWidgets.QStyle.StateFlag.State_HasFocus
                
                # 2. Pintamos nuestro propio fondo
                painter.save()
                painter.setPen(QtCore.Qt.PenStyle.NoPen)

                painter.setBrush(QtGui.QColor(12, 140, 233, 153)) # <-Se modifica el color de fondo para la seleccion de color
                
                # Dibujamos un rectángulo con bordes redondeados (6px) para que coincida con el QSS
                painter.drawRoundedRect(opt.rect, 4, 4)
                painter.restore()
                
                # 3. Forzamos que el texto sea blanco para que contraste con el fondo azul
                opt.palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#ffffff"))

            # 4. Le devolvemos el control a Qt para que dibuje el texto y el ícono 
            super().paint(painter, opt, index)
        except Exception as e:
            print(f"Error en NeonSelectionDelegate: {e}")
            try: super().paint(painter, option, index)
            except: pass

    def updateEditorGeometry(self, editor, option, index):
        """Secuestra la geometría del QLineEdit al renombrar para hacerlo más grande"""
        rect = option.rect
        
        # Expandimos el rectángulo: ajustamos los márgenes (izquierda, arriba, derecha, abajo)
        # Valores negativos expanden hacia afuera.
        rect.adjust(-1, -1, 10, 1) 
        
        editor.setGeometry(rect)

class NeonProxyStyle(QtWidgets.QProxyStyle):
    """
    Estilo proxy global que secuestra el motor de dibujo de Qt.
    Su función principal es erradicar el rectángulo/sombreado nativo 
    de foco (Tabulador) en todos los widgets de la aplicación.
    Y controlar el estado de las 'flechitas' de despliegue en el menu de los botones
    """
    def __init__(self, style=None):
        super().__init__(style)
        # Precargamos el SVG en memoria para no leer el disco cada vez que se dibuja un botón
        self.arrow_down_renderer = QtSvg.QSvgRenderer(resource_path("resources/icons/flecha_abajo.svg"))

    def drawPrimitive(self, element, option, painter, widget=None):
        # PE_FrameFocusRect es el nombre interno del sombreado de foco nativo
        if element == QtWidgets.QStyle.PrimitiveElement.PE_FrameFocusRect:
            # Al hacer return sin llamar a super(), el sombreado simplemente nunca se dibuja.
            return 

        if element in (QtWidgets.QStyle.PrimitiveElement.PE_IndicatorArrowDown, QtWidgets.QStyle.PrimitiveElement.PE_IndicatorButtonDropDown):
        
            # Qt nos entrega 'option.rect', que es la caja invisible PERFECTA
            rect = option.rect
            # Calculamos su tamaño 
            size = 8
            x = rect.center().x() - (size / 2)
            y = rect.center().y() - (size / 2)
            custom_rect = QtCore.QRectF(x, y, size, size)

            # Usamos nuestro SVG en lugar de la brocha nativa de Qt
            self.arrow_down_renderer.render(painter, custom_rect)
            return
        
        # Para todo lo demás, dejamos que Qt dibuje normalmente
        try:
            super().drawPrimitive(element, option, painter, widget)
        except RuntimeError:
            pass

class CustomSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Ocultar los botones de flecha integrados
        self.setButtonSymbols(QtWidgets.QSpinBox.ButtonSymbols.NoButtons)
        # Cursor de texto (I-Beam) o puntero al pasar el mouse
        self.setCursor(QtCore.Qt.CursorShape.IBeamCursor)
        # Alineacion al centro
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

class CustomComboBox(QtWidgets.QComboBox):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        opt = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(opt)

        # 1. Dibuja el marco, fondo y flecha nativos/QSS (vaciando el texto temporalmente)
        current_text = opt.currentText
        opt.currentText = ""
        self.style().drawComplexControl(QtWidgets.QStyle.ComplexControl.CC_ComboBox, opt, painter, self)

        # 2. Calcula el área interior del texto (descontando bordes y flecha)
        text_rect = self.style().subControlRect(
            QtWidgets.QStyle.ComplexControl.CC_ComboBox,
            opt,
            QtWidgets.QStyle.SubControl.SC_ComboBoxEditField,
            self
        )

        # 3. Dibuja el texto seleccionado centrado horizontal y verticalmente
        opt.currentText = current_text
        self.style().drawItemText(
            painter,
            text_rect,
            QtCore.Qt.AlignmentFlag.AlignCenter,
            self.palette(),
            self.isEnabled(),
            opt.currentText
        )

class CustomCheckBox(QtWidgets.QCheckBox):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

class CustomPushButton(QtWidgets.QPushButton):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)