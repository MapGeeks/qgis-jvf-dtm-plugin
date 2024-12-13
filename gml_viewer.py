# gml_viewer.py
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.PyQt.QtGui import QIcon,QColor 
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt,QVariant
from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsRuleBasedRenderer,QgsSingleSymbolRenderer,QgsCategorizedSymbolRenderer, QgsGraduatedSymbolRenderer,
                      QgsProject, QgsCoordinateTransformContext,  QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsCoordinateTransform)
import os.path
import subprocess
from .czech_dtm_parser import CzechDTMParser
                        
class GMLViewer:
    """QGIS Plugin Implementation."""
    
    def __init__(self, iface):
        """Constructor."""
        # Save reference to the QGIS interface
        self.iface = iface
        
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        # initialize locale
        self.locale = QSettings().value('locale/userLocale', '')
        if self.locale:
            # Get first two letters of locale if it exists
            self.locale = self.locale[0:2]
        else:
            # If locale not set, default to 'en'
            self.locale = 'en'
            
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'GMLViewer_{self.locale}.qm')

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = 'JVF DTM Viewer'
        
        # Check if plugin was started the first time in current QGIS session
        self.first_start = None
        
        # Initialize parser
        
        self.parser = CzechDTMParser(self.iface)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                  add_to_menu=True, add_to_toolbar=True, status_tip=None,
                  whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside QGIS."""
        icon_path = os.path.join(self.plugin_dir, 'iconIn.png')
        self.add_action(
            icon_path,
            text="Open JVF DTM Viewer",
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.menu,
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select JVF File",
            "",
            "JVF files XML files (*.xml);;All files (*.*)"
        )
        
        if filename:
            success, message = self.parser.parse_file(filename)
            
            msgBox = QMessageBox()
            msgBox.setText(message)
            if (success == False) :
            
                msgBox.setIcon(QMessageBox.Critical)
                msgBox.exec()
    
