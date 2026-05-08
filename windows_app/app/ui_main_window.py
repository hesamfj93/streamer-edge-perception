# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QApplication, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMenuBar,
    QPushButton, QSizePolicy, QStatusBar, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(804, 756)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.groupBoxControls = QGroupBox(self.centralwidget)
        self.groupBoxControls.setObjectName(u"groupBoxControls")
        self.gridLayout = QGridLayout(self.groupBoxControls)
        self.gridLayout.setObjectName(u"gridLayout")
        self.btnStop = QPushButton(self.groupBoxControls)
        self.btnStop.setObjectName(u"btnStop")

        self.gridLayout.addWidget(self.btnStop, 4, 2, 1, 1)

        self.lblImgsz = QLabel(self.groupBoxControls)
        self.lblImgsz.setObjectName(u"lblImgsz")

        self.gridLayout.addWidget(self.lblImgsz, 1, 1, 1, 1)

        self.lblState = QLabel(self.groupBoxControls)
        self.lblState.setObjectName(u"lblState")

        self.gridLayout.addWidget(self.lblState, 0, 1, 1, 1)

        self.lblFps = QLabel(self.groupBoxControls)
        self.lblFps.setObjectName(u"lblFps")

        self.gridLayout.addWidget(self.lblFps, 3, 1, 1, 1)

        self.btnSet640 = QPushButton(self.groupBoxControls)
        self.btnSet640.setObjectName(u"btnSet640")

        self.gridLayout.addWidget(self.btnSet640, 5, 1, 1, 1)

        self.btnSet1280 = QPushButton(self.groupBoxControls)
        self.btnSet1280.setObjectName(u"btnSet1280")

        self.gridLayout.addWidget(self.btnSet1280, 5, 2, 1, 1)

        self.editConf = QLineEdit(self.groupBoxControls)
        self.editConf.setObjectName(u"editConf")

        self.gridLayout.addWidget(self.editConf, 5, 0, 1, 1)

        self.lblConf = QLabel(self.groupBoxControls)
        self.lblConf.setObjectName(u"lblConf")

        self.gridLayout.addWidget(self.lblConf, 2, 1, 1, 1)

        self.label_3 = QLabel(self.groupBoxControls)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.label_2 = QLabel(self.groupBoxControls)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.editImgsz = QLineEdit(self.groupBoxControls)
        self.editImgsz.setObjectName(u"editImgsz")

        self.gridLayout.addWidget(self.editImgsz, 4, 0, 1, 1)

        self.label_4 = QLabel(self.groupBoxControls)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)

        self.label = QLabel(self.groupBoxControls)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.btnStart = QPushButton(self.groupBoxControls)
        self.btnStart.setObjectName(u"btnStart")

        self.gridLayout.addWidget(self.btnStart, 4, 1, 1, 1)

        self.btnApply = QPushButton(self.groupBoxControls)
        self.btnApply.setObjectName(u"btnApply")

        self.gridLayout.addWidget(self.btnApply, 4, 3, 1, 1)


        self.verticalLayout.addWidget(self.groupBoxControls)

        self.groupBoxVideo = QGroupBox(self.centralwidget)
        self.groupBoxVideo.setObjectName(u"groupBoxVideo")
        self.verticalLayout_2 = QVBoxLayout(self.groupBoxVideo)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.editVideoUrl = QLineEdit(self.groupBoxVideo)
        self.editVideoUrl.setObjectName(u"editVideoUrl")

        self.verticalLayout_2.addWidget(self.editVideoUrl)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.btnOpenVideo = QPushButton(self.groupBoxVideo)
        self.btnOpenVideo.setObjectName(u"btnOpenVideo")

        self.horizontalLayout.addWidget(self.btnOpenVideo)

        self.btnPlay = QPushButton(self.groupBoxVideo)
        self.btnPlay.setObjectName(u"btnPlay")

        self.horizontalLayout.addWidget(self.btnPlay)

        self.btnStopVideo = QPushButton(self.groupBoxVideo)
        self.btnStopVideo.setObjectName(u"btnStopVideo")

        self.horizontalLayout.addWidget(self.btnStopVideo)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.videoWidget = QVideoWidget(self.groupBoxVideo)
        self.videoWidget.setObjectName(u"videoWidget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.videoWidget.sizePolicy().hasHeightForWidth())
        self.videoWidget.setSizePolicy(sizePolicy)

        self.verticalLayout_2.addWidget(self.videoWidget)


        self.verticalLayout.addWidget(self.groupBoxVideo)

        self.groupBoxMqtt = QGroupBox(self.centralwidget)
        self.groupBoxMqtt.setObjectName(u"groupBoxMqtt")
        self.gridLayout_2 = QGridLayout(self.groupBoxMqtt)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.label_10 = QLabel(self.groupBoxMqtt)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_2.addWidget(self.label_10, 1, 0, 1, 1)

        self.editPrefix = QLineEdit(self.groupBoxMqtt)
        self.editPrefix.setObjectName(u"editPrefix")

        self.gridLayout_2.addWidget(self.editPrefix, 1, 3, 1, 1)

        self.label_9 = QLabel(self.groupBoxMqtt)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_2.addWidget(self.label_9, 0, 0, 1, 3)

        self.editBroker = QLineEdit(self.groupBoxMqtt)
        self.editBroker.setObjectName(u"editBroker")

        self.gridLayout_2.addWidget(self.editBroker, 0, 3, 1, 1)

        self.btnConnectMqtt = QPushButton(self.groupBoxMqtt)
        self.btnConnectMqtt.setObjectName(u"btnConnectMqtt")

        self.gridLayout_2.addWidget(self.btnConnectMqtt, 2, 0, 1, 1)

        self.lblMqtt = QLabel(self.groupBoxMqtt)
        self.lblMqtt.setObjectName(u"lblMqtt")

        self.gridLayout_2.addWidget(self.lblMqtt, 2, 2, 1, 1)


        self.verticalLayout.addWidget(self.groupBoxMqtt)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 804, 33))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.groupBoxControls.setTitle(QCoreApplication.translate("MainWindow", u"Controls", None))
        self.btnStop.setText(QCoreApplication.translate("MainWindow", u"Stop", None))
        self.lblImgsz.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.lblState.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.lblFps.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.btnSet640.setText(QCoreApplication.translate("MainWindow", u"Set 640", None))
        self.btnSet1280.setText(QCoreApplication.translate("MainWindow", u"Set 1280", None))
        self.editConf.setText(QCoreApplication.translate("MainWindow", u"0.25", None))
        self.lblConf.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"conf:", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"imgsz:", None))
        self.editImgsz.setText(QCoreApplication.translate("MainWindow", u"640", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"FPS:", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"State:", None))
        self.btnStart.setText(QCoreApplication.translate("MainWindow", u"Start", None))
        self.btnApply.setText(QCoreApplication.translate("MainWindow", u"Apply", None))
        self.groupBoxVideo.setTitle(QCoreApplication.translate("MainWindow", u"Video", None))
        self.editVideoUrl.setText(QCoreApplication.translate("MainWindow", u"rtsp://...", None))
        self.btnOpenVideo.setText(QCoreApplication.translate("MainWindow", u"Open", None))
        self.btnPlay.setText(QCoreApplication.translate("MainWindow", u"Play/Pause", None))
        self.btnStopVideo.setText(QCoreApplication.translate("MainWindow", u"Stop", None))
        self.groupBoxMqtt.setTitle(QCoreApplication.translate("MainWindow", u"MQTT", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"Topic Prefix:", None))
        self.editPrefix.setText(QCoreApplication.translate("MainWindow", u"projectA/jetson-01", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"Broker:", None))
        self.editBroker.setText(QCoreApplication.translate("MainWindow", u"192.168.50.1", None))
        self.btnConnectMqtt.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.lblMqtt.setText(QCoreApplication.translate("MainWindow", u"disconnected", None))
    # retranslateUi

