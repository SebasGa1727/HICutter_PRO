from PyQt6 import QtWidgets, QtGui, QtCore

class EditorToolbar(QtWidgets.QToolBar):
    """
    Componente visual independiente para la barra de herramientas del editor.
    Pricesa solo los botones y señales
    """
    # Generaremos señales que enviaran una peticion anuestro main
    sig_reset_requested = QtCore.pyqtSignal()
    sig_rotate_right_requested = QtCore.pyqtSignal()
    sig_rotate_left_requested = QtCore.pyqtSignal()
    sig_rotate_180_requested = QtCore.pyqtSignal()
    sig_cancel_requested = QtCore.pyqtSignal()

    def __init__(self, parent = None) -> None:
        # Inicializamos la clase padre "toolbar" y le brindamos de apodo
        # "Herramientas de edicion"
        super().__init__("Herramientas de Edicion", parent)
        #Declaramos las "Shortcuts"
        self.KEY_RESTART_POINTS = "esc"
        self.KEY_RIGHT_ROTATE = "a"

        self._setup_actions()
    
    def _setup_actions(self):
        '''Crea las acciones, brinda la estructura y 
        conecta las señales definidas al inicio de la clase'''

        #Creamos el objeto space tipo qtwidgets para darle propiedades de espaciado y llamarlo despues
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

        # Boton "Reiniciar puntos"
        self.reset_action = QtGui.QAction('Reiniciar puntos', self)
        # Genera un recuadro flotante diciendo que hace este boton
        self.reset_action.setToolTip("Reinicia los todos los puntos colocados")
        self.reset_action.setShortcut(self.KEY_RESTART_POINTS)
        # Al presionar(.triggered), disparamos(.emit) nuestra señal
        self.reset_action.triggered.connect(self.sig_reset_requested.emit)
        self.addAction(self.reset_action)

        self.addSeparator() # <- Agrega una linea vertical (espacio), para dar estructura

        self.rotate_right_action = QtGui.QAction('Rotar 90° →', self)
        self.rotate_right_action.setToolTip("Rotar imagen 90° a la derecha")
        # Le asignamos atajos "Shortcuts" y un solo atajo "Shortcut"
        self.rotate_right_action.setShortcut(self.KEY_RIGHT_ROTATE)
        self.rotate_right_action.triggered.connect(self.sig_rotate_right_requested.emit)
        self.addAction(self.rotate_right_action)

        self.rotate_left_action = QtGui.QAction('Rotar 90° ←', self)
        self.rotate_left_action.setToolTip("Rotar imagen 90° a la izquierda")
        self.rotate_left_action.triggered.connect(self.sig_rotate_left_requested.emit)
        self.addAction(self.rotate_left_action)

        self.rotate_180_action = QtGui.QAction('Rotar 180°', self)
        self.rotate_180_action.setToolTip("Rotar imagen 180°")
        self.rotate_180_action.triggered.connect(self.sig_rotate_180_requested.emit)
        self.addAction(self.rotate_180_action)

        self.addWidget(spacer) #Añadimos el espacio para que empuje todo lo de abajo al lado derecho

        self.cancel_action = QtGui.QAction('Cancelar', self)
        self.cancel_action.setToolTip("Abortar edicion y volver al menu principal")
        self.cancel_action.triggered.connect(self.sig_cancel_requested.emit)
        self.addAction(self.cancel_action)
        #Le inyectamos el ID para que obtenga el formato css definido en la parte superior
        cancel_button_widget = self.widgetForAction(self.cancel_action)
        if cancel_button_widget:
            cancel_button_widget.setProperty("estilo", "cancelar") #Aqui le asignamos el ID en la parte superior

    def set_editor_active(self, is_active: bool) -> None:
        '''Metodo para encender/apagar la visalizacion y funcionalidad de la toolbar'''

        self.setVisible(is_active)
        self.setEnabled(is_active)