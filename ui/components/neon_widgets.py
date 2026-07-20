from PyQt6 import QtWidgets, QtCore, QtGui

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
            print(f"Error en 'drawBranches': {e}")
    
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
                
                # 2. Pintamos nuestro propio fondo (Tu azul con 60% de opacidad)
                painter.save()
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                # rgba(12, 140, 233, 0.6) -> 0.6 * 255 = ~153 (Alfa)
                painter.setBrush(QtGui.QColor(12, 140, 233, 153)) # <-Aqui se modifica el color de fondo para la seleccion de color
                
                # Dibujamos un rectángulo con bordes redondeados (6px) para que coincida con tu QSS
                painter.drawRoundedRect(opt.rect, 4, 4)
                painter.restore()
                
                # 3. Forzamos que el texto sea blanco para que contraste con el fondo azul
                opt.palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#ffffff"))

            # 4. Le devolvemos el control a Qt para que dibuje el texto y el ícono 
            # (pero como ya le quitamos la bandera de selección, no dibujará el fondo nativo)
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
    """
    def drawPrimitive(self, element, option, painter, widget=None):
        # PE_FrameFocusRect es el nombre interno del sombreado de foco nativo
        if element == QtWidgets.QStyle.PrimitiveElement.PE_FrameFocusRect:
            # Al hacer return sin llamar a super(), el sombreado simplemente nunca se dibuja.
            return 
        
        # Para todo lo demás, dejamos que Qt dibuje normalmente
        super().drawPrimitive(element, option, painter, widget)