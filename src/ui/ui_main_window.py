# src/ui/ui_main_window.py

# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMenu,
    QMenuBar, QSizePolicy, QSplitter, QStackedWidget,
    QStatusBar, QTableWidget, QTableWidgetItem, QTreeView,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(900, 650)
        self.action_settings = QAction(MainWindow)
        self.action_settings.setObjectName(u"action_settings")
        self.action_about = QAction(MainWindow)
        self.action_about.setObjectName(u"action_about")
        self.action_open_config = QAction(MainWindow)
        self.action_open_config.setObjectName(u"action_open_config")
        self.action_edit = QAction(MainWindow)
        self.action_edit.setObjectName(u"action_edit")
        self.action_sourcing = QAction(MainWindow)
        self.action_sourcing.setObjectName(u"action_sourcing")
        self.action_historical = QAction(MainWindow)
        self.action_historical.setObjectName(u"action_historical")
        self.action_dashboard = QAction(MainWindow)
        self.action_dashboard.setObjectName(u"action_dashboard")
        self.action_dashboard.setMenuRole(QAction.MenuRole.NoRole)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_main = QGridLayout(self.centralwidget)
        self.gridLayout_main.setObjectName(u"gridLayout_main")
        self.gridLayout_main.setContentsMargins(10, 10, 10, 10)
        self.main_stack = QStackedWidget(self.centralwidget)
        self.main_stack.setObjectName(u"main_stack")
        self.dashboard_page = QWidget()
        self.dashboard_page.setObjectName(u"dashboard_page")
        self.gridLayout_dash = QGridLayout(self.dashboard_page)
        self.gridLayout_dash.setObjectName(u"gridLayout_dash")
        self.label = QLabel(self.dashboard_page)
        self.label.setObjectName(u"label")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_dash.addWidget(self.label, 0, 0, 1, 1)

        self.main_stack.addWidget(self.dashboard_page)
        self.sourcing_page = QWidget()
        self.sourcing_page.setObjectName(u"sourcing_page")
        self.horizontalLayout_sourcing = QHBoxLayout(self.sourcing_page)
        self.horizontalLayout_sourcing.setSpacing(5)
        self.horizontalLayout_sourcing.setObjectName(u"horizontalLayout_sourcing")
        self.horizontalLayout_sourcing.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(self.sourcing_page)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.left_container = QWidget(self.splitter)
        self.left_container.setObjectName(u"left_container")
        self.left_container.setMaximumSize(QSize(400, 16777215))
        self.verticalLayout_menu = QVBoxLayout(self.left_container)
        self.verticalLayout_menu.setObjectName(u"verticalLayout_menu")
        self.verticalLayout_menu.setContentsMargins(0, 0, 5, 0)
        self.lbl_categories = QLabel(self.left_container)
        self.lbl_categories.setObjectName(u"lbl_categories")
        font = QFont()
        font.setBold(True)
        self.lbl_categories.setFont(font)

        self.verticalLayout_menu.addWidget(self.lbl_categories)

        self.tree_categories = QTreeView(self.left_container)
        self.tree_categories.setObjectName(u"tree_categories")
        self.tree_categories.setAnimated(True)
        self.tree_categories.setHeaderHidden(True)

        self.verticalLayout_menu.addWidget(self.tree_categories)

        self.splitter.addWidget(self.left_container)
        self.right_container = QWidget(self.splitter)
        self.right_container.setObjectName(u"right_container")
        self.verticalLayout_results = QVBoxLayout(self.right_container)
        self.verticalLayout_results.setObjectName(u"verticalLayout_results")
        self.verticalLayout_results.setContentsMargins(5, 0, 0, 0)
        self.lbl_results = QLabel(self.right_container)
        self.lbl_results.setObjectName(u"lbl_results")
        self.lbl_results.setFont(font)

        self.verticalLayout_results.addWidget(self.lbl_results)

        self.table_sourcing_data = QTableWidget(self.right_container)
        if (self.table_sourcing_data.columnCount() < 5):
            self.table_sourcing_data.setColumnCount(5)
        __qtablewidgetitem = QTableWidgetItem()
        self.table_sourcing_data.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.table_sourcing_data.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.table_sourcing_data.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.table_sourcing_data.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.table_sourcing_data.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        self.table_sourcing_data.setObjectName(u"table_sourcing_data")
        self.table_sourcing_data.setAlternatingRowColors(True)
        self.table_sourcing_data.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.verticalLayout_results.addWidget(self.table_sourcing_data)

        self.splitter.addWidget(self.right_container)

        self.horizontalLayout_sourcing.addWidget(self.splitter)

        self.main_stack.addWidget(self.sourcing_page)
        self.historical_page = QWidget()
        self.historical_page.setObjectName(u"historical_page")
        self.horizontalLayout_historical = QHBoxLayout(self.historical_page)
        self.horizontalLayout_historical.setSpacing(5)
        self.horizontalLayout_historical.setObjectName(u"horizontalLayout_historical")
        self.horizontalLayout_historical.setContentsMargins(0, 0, 0, 0)
        self.splitter_historical = QSplitter(self.historical_page)
        self.splitter_historical.setObjectName(u"splitter_historical")
        self.splitter_historical.setOrientation(Qt.Orientation.Horizontal)
        self.left_container_historical = QWidget(self.splitter_historical)
        self.left_container_historical.setObjectName(u"left_container_historical")
        self.left_container_historical.setMaximumSize(QSize(400, 16777215))
        self.verticalLayout_menu_historical = QVBoxLayout(self.left_container_historical)
        self.verticalLayout_menu_historical.setObjectName(u"verticalLayout_menu_historical")
        self.verticalLayout_menu_historical.setContentsMargins(0, 0, 5, 0)
        self.lbl_categories_historical = QLabel(self.left_container_historical)
        self.lbl_categories_historical.setObjectName(u"lbl_categories_historical")
        self.lbl_categories_historical.setFont(font)

        self.verticalLayout_menu_historical.addWidget(self.lbl_categories_historical)

        self.tree_categories_historical = QTreeView(self.left_container_historical)
        self.tree_categories_historical.setObjectName(u"tree_categories_historical")
        self.tree_categories_historical.setAnimated(True)
        self.tree_categories_historical.setHeaderHidden(True)

        self.verticalLayout_menu_historical.addWidget(self.tree_categories_historical)

        self.splitter_historical.addWidget(self.left_container_historical)
        self.right_container_historical = QWidget(self.splitter_historical)
        self.right_container_historical.setObjectName(u"right_container_historical")
        self.verticalLayout_results_historical = QVBoxLayout(self.right_container_historical)
        self.verticalLayout_results_historical.setObjectName(u"verticalLayout_results_historical")
        self.verticalLayout_results_historical.setContentsMargins(5, 0, 0, 0)
        self.lbl_results_historical = QLabel(self.right_container_historical)
        self.lbl_results_historical.setObjectName(u"lbl_results_historical")
        self.lbl_results_historical.setFont(font)

        self.verticalLayout_results_historical.addWidget(self.lbl_results_historical)

        self.table_historical_data = QTableWidget(self.right_container_historical)
        if (self.table_historical_data.columnCount() < 5):
            self.table_historical_data.setColumnCount(5)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.table_historical_data.setHorizontalHeaderItem(0, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.table_historical_data.setHorizontalHeaderItem(1, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.table_historical_data.setHorizontalHeaderItem(2, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.table_historical_data.setHorizontalHeaderItem(3, __qtablewidgetitem8)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.table_historical_data.setHorizontalHeaderItem(4, __qtablewidgetitem9)
        self.table_historical_data.setObjectName(u"table_historical_data")
        self.table_historical_data.setAlternatingRowColors(True)
        self.table_historical_data.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.verticalLayout_results_historical.addWidget(self.table_historical_data)

        self.splitter_historical.addWidget(self.right_container_historical)

        self.horizontalLayout_historical.addWidget(self.splitter_historical)

        self.main_stack.addWidget(self.historical_page)

        self.gridLayout_main.addWidget(self.main_stack, 0, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 900, 27))
        self.menu_Help = QMenu(self.menubar)
        self.menu_Help.setObjectName(u"menu_Help")
        self.menu_Mode = QMenu(self.menubar)
        self.menu_Mode.setObjectName(u"menu_Mode")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menu_Mode.menuAction())
        self.menubar.addAction(self.menu_Help.menuAction())
        self.menu_Help.addAction(self.action_settings)
        self.menu_Help.addAction(self.action_about)
        self.menu_Mode.addAction(self.action_dashboard)
        self.menu_Mode.addAction(self.action_historical)
        self.menu_Mode.addAction(self.action_sourcing)

        self.retranslateUi(MainWindow)

        self.main_stack.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Sourcing Application", None))
        self.action_settings.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.action_about.setText(QCoreApplication.translate("MainWindow", u"About ...", None))
        self.action_open_config.setText(QCoreApplication.translate("MainWindow", u"&Open Config", None))
        self.action_edit.setText(QCoreApplication.translate("MainWindow", u"&Exit", None))
        self.action_sourcing.setText(QCoreApplication.translate("MainWindow", u"&Sourcing", None))
        self.action_historical.setText(QCoreApplication.translate("MainWindow", u"&Historical", None))
        self.action_dashboard.setText(QCoreApplication.translate("MainWindow", u"&Dashboard", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Dashboard Page", None))
        self.lbl_categories.setText(QCoreApplication.translate("MainWindow", u"Search Categories", None))
        self.lbl_results.setText(QCoreApplication.translate("MainWindow", u"Sourcing Results Matrix", None))
        ___qtablewidgetitem = self.table_sourcing_data.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"ID", None))
        ___qtablewidgetitem1 = self.table_sourcing_data.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Supplier", None))
        ___qtablewidgetitem2 = self.table_sourcing_data.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"Category Part", None))
        ___qtablewidgetitem3 = self.table_sourcing_data.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Lead Time", None))
        ___qtablewidgetitem4 = self.table_sourcing_data.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"Budget / Cost", None))
        self.lbl_categories_historical.setText(QCoreApplication.translate("MainWindow", u"Historical Categories", None))
        self.lbl_results_historical.setText(QCoreApplication.translate("MainWindow", u"Historical Pricing Data Archive", None))
        ___qtablewidgetitem5 = self.table_historical_data.horizontalHeaderItem(0)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MainWindow", u"ID", None))
        ___qtablewidgetitem6 = self.table_historical_data.horizontalHeaderItem(1)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("MainWindow", u"Supplier", None))
        ___qtablewidgetitem7 = self.table_historical_data.horizontalHeaderItem(2)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("MainWindow", u"Category Part", None))
        ___qtablewidgetitem8 = self.table_historical_data.horizontalHeaderItem(3)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("MainWindow", u"Lead Time", None))
        ___qtablewidgetitem9 = self.table_historical_data.horizontalHeaderItem(4)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("MainWindow", u"Budget / Cost", None))
        self.menu_Help.setTitle(QCoreApplication.translate("MainWindow", u"&Help", None))
        self.menu_Mode.setTitle(QCoreApplication.translate("MainWindow", u"&Mode", None))
    # retranslateUi

