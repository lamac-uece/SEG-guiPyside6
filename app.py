from collections import namedtuple
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import cv2 as cv2
from matplotlib import pyplot as plt
import skimage.filters.edges
# import pydicom.encoders.gdcm
# import gdcm
# from libjpeg import decode_pixel_data
# import pydicom.encoders.pylibjpeg
import pydicom.pixel_data_handlers.pylibjpeg_handler
from skimage.segmentation import mark_boundaries
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvas
from functions import _Mode
from functions import *
import copy
from PIL import Image
from os import path
from scipy.ndimage import binary_fill_holes
area = 1
saveDir = ""
openDir = ""
graph = ""
# The superpixel mask is here
undo = 0
segments_global = []
# The Painted(rgb) mask is here
mask3d  = []
# The backups mask3d is here. Is used to rollback in case of wrong paints.
previous_paints = []
# Defines if the paint are enabled
superpixel_auth = False
# Defines the current color of the superpixel paint
colorvec = np.array([255, 255, 0])
# Defines if the 'mask3d' or 'masks' variables needs to be created again
masks_empty = True
# Aproximated number of superpixels segments
multiplicator = 1.0
numSegments = 2000
sigma_slic = 1
compactness = 0.05
nbins = 256
clip_limit = 0.03
max_num_iter=10
min_size_factor=0.5
max_size_factor=3
segmentedMask =[]
currentTissue = 0
informacoes = {"colors":[], "identifier":[], "tissue":[]}
previous_segments = {"superpixel":[], "previous_identifier":[]}
dictTissues = {"Fat":1,"Intramuscular Fat":2, "Visceral Fat":3, "Bone":4, "Muscle":5, "Organ":6, "Other": 7}
currentPlot = 0
csvFlag = False
show_superpixel = True  # inicia como visível
toggle_available = False

muscle_hu = []
fat_hu = []
selected_hu = []
radio_density_check_enabled = True  # Controla se a verificação de HU está ativa

# Click event for paint superpixel
def mouse_event(event, plot=int):
    global segments_global
    global superpixel_auth
    if ((event.xdata != None or event.ydata != None) 
    and ((event.xdata > 1 and event.ydata >1)) 
    and (superpixel_auth == True) 
    and (
        (
        (str(imageViewer.plotsuperpixelmask.toolbar._actions["zoom"]).__contains__("checked=false"))
        and (str(imageViewer.plotsuperpixelmask.toolbar._actions["pan"]).__contains__("checked=false"))
        and currentPlot == 0
        )
    or 
        (
        (str(imageViewer.plotwidget_modify.toolbar._actions["zoom"]).__contains__("checked=false"))
        and (str(imageViewer.plotwidget_modify.toolbar._actions["pan"]).__contains__("checked=false"))
        and currentPlot == 1
        ))
    ): 
        paintSuperPixel(event.xdata,event.ydata,segments_global, plot)

def paintSuperPixel(x,y,segments, plot=int):
    global masks
    # fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(6, 6))
    global mask3d 
    global previous_paints
    global previous_segments
    global colorvec
    global masks_empty
    global segmentedMask
    global informacoes
    global currentTissue
    global fat_hu
    global muscle_hu
    global radio_density_check_enabled
    if(segments[int(y)][int(x)] == 0):
        return
    if(np.array_equal(segmentedMask, [])):
        segmentedMask = np.zeros_like(dicom_image_array, dtype="uint8")
    if(masks_empty):
        # Creates a new 3d mask with the shape of the dicom image array
        mask3d = np.zeros((dicom_image_array.shape[0],dicom_image_array.shape[1],3), dtype = "uint8")
        mask3d[:,:,0] = dicom_image_array 
        mask3d[:,:,1] = dicom_image_array 
        mask3d[:,:,2] = dicom_image_array
        masks_empty = False
    masks = np.zeros_like(dicom_image_array, dtype="bool")
    # Store a copy of mask3d for rollback
    previous_paints.append(copy.deepcopy(mask3d))
    segment_id = segments[int(y)][int(x)]

    previous_segments["superpixel"].append(segment_id)
    previous_segments["previous_identifier"].append(segmentedMask[int(y)][int(x)])
    # Verify if exists more than 10 copies, for delete the older
    if(previous_paints.__len__() == 11):
            previous_paints.__delitem__(0)
            previous_segments["superpixel"].__delitem__(0)
            previous_segments["previous_identifier"].__delitem__(0)
    if((plot == 1 and undo == 1) or(plot == 2 and undo == 2) or undo == 3):
        masks = np.ones_like(dicom_image_array, dtype="bool")
        segmentedMask[segments==segments[int(y)][int(x)]] = 0       
        # Verify what segments of segments global are equals to 
        # the clicked segment to change this masks elements to 1, 
        # instead of false
        masks[segments == segments[int(y)][int(x)]] = 0
        # show the masked region
        ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 

        mask3d[:,:,0] = dicom_image_array  * (~masks).astype('uint8') + mask3d[:,:,0]*(masks).astype('uint8')
        mask3d[:,:,1] = dicom_image_array  * (~masks).astype('uint8') + mask3d[:,:,1]*(masks).astype('uint8')
        mask3d[:,:,2] = dicom_image_array  * (~masks).astype('uint8') + mask3d[:,:,2]*(masks).astype('uint8')
    else:
        hu_mask = np.ones_like(dicom_image_array, dtype=bool)        
        if radio_density_check_enabled :
            if informacoes["tissue"][currentTissue - 1] in [1, 2, 3] :
                
                hu_mask = hu_mask * fat_hu
            elif informacoes["tissue"][currentTissue - 1] in [5]:
                hu_mask = hu_mask * muscle_hu
                
        segmentedMask[(hu_mask * segments)==segments[int(y)][int(x)]] = currentTissue            
        # Verify what segments of segments global are equals to 
        # the clicked segment to change this masks elements to 1, 
        # instead of false
        masks[(hu_mask * segments) == segments[int(y)][int(x)]] = 1
        # show the masked region
        ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 

        mask3d[:,:,0] = informacoes['colors'][currentTissue -1][0] * masks + mask3d[:,:,0]*(~masks).astype('uint8')
        mask3d[:,:,1] = informacoes['colors'][currentTissue -1][1] * masks + mask3d[:,:,1]*(~masks).astype('uint8')
        mask3d[:,:,2] = informacoes['colors'][currentTissue -1][2] * masks + mask3d[:,:,2]*(~masks).astype('uint8')
        
    # Update the mask with the new rgb mask(with the new painted superpixel)
    imageViewer.plotsuperpixelmask.UpdateView()

# Here are stored the path of the opened file    
fileName_global = ''    
# fileName_global = "C:/Users/LUIAN/Desktop/SegPy/SEG-guiPyside6/images/000003.dcm"
# dicom_image_array = dicom2array(pydicom.dcmread(fileName_global, force=True))
# dicom_image_array =  ConvertToUint8(dicom_image_array)

# Here are stored the array of the dicom image(both original, 
# with removed objects and with CLAHE applied)
dicom_image_array = []

masks =[]

COLORS = [
    '#ffeeb9',
    '#bd4b4b',
    '#442242',
    '#1ab11d',
    '#286440',
    '#133542',
    '#675c85',
    '#251e3c',
    '#1e132c',
    '#b5b4d3',
    '#6b6a7c',
    '#232328'
]
class PercentagesGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.view = FigureCanvas(Figure(figsize=(10, 6)))
        self.axes = self.view.figure.subplots()
        self.axes.set_title("Tissues/percentages")
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        self.setLayout(vlayout) 
    def calculatePercentages(self):
        global segmentedMask
        global mask3d
        global informacoes
        global dictTissues
        global area
        if(not (np.array_equal(mask3d, []) 
        or np.array_equal(segmentedMask, []))):
            totalpixels = area
            labels = []
            sizes = []
            listKeys = list(dictTissues.keys())
            listValues = list(dictTissues.values())
            for i in range(informacoes["tissue"].__len__()):
                tissue = informacoes["tissue"][i]
                identifier = informacoes["identifier"][i]
                labels.append(listKeys[listValues.index(tissue)])
                pixels = np.count_nonzero(segmentedMask == identifier)
                totalpixels = totalpixels - pixels
                sizes.append(pixels)
            sizes.append(totalpixels)
            labels.append("Unsegmented")
            sizes[:] = [100*x / sum(sizes) for x in sizes]
            colors = []
            colors[:] = [[color[0]/255, color[1]/255, color[2]/255] for color in informacoes["colors"]]
            colors.append([50/255,50/255,50/255])
            xlables = []
            xlables[:] = [f"{labels[i]}\n{np.round(sizes[i], 2)}%" for i in range(sizes.__len__())]
            x = np.arange(len(sizes))
            self.axes.bar(x, sizes, color=colors, linewidth=0.2, edgecolor=[0,0,0])
            self.axes.set_xticks(x)
            self.axes.set_xticklabels(labels)
            self.axes.set_xticklabels(xlables)
            self.axes.set_xlabel('Tissues')
            self.axes.set_ylabel('Percentages')
            self.view.draw()
class Form(QDialog):
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)
        global numSegments
        global sigma_slic
        global compactness
        global clip_limit
        global nbins
        global max_num_iter
        global min_size_factor
        global max_size_factor
        global multiplicator
        self.setWindowTitle("Parâmetros")
        self.labelSuperpixel = QLabel("<h1>Superpixel</h1>")
        self.labelClahe = QLabel("<h1>Clahe</h1>")
        self.labelSkin = QLabel("<h1>Skin Segmentation</h1>")
        self.label1 = QLabel("Superpixels")
        self.input1 = QLineEdit(str(numSegments))
        self.input1.setValidator(QIntValidator(1000, 10000))
        self.label2 = QLabel("Compactness")
        self.input2 = QDoubleSpinBox()
        self.input2.setValue(compactness)
        self.input2.setMaximum(100)
        self.label3 = QLabel("sigma")
        self.input3 = QLineEdit(str(sigma_slic))
        self.input3.setValidator(QIntValidator(0, 10))
        self.label4 = QLabel("Clip limit(CLAHE)") 
        self.input4 = QDoubleSpinBox()
        self.input4.setValue(clip_limit)
        self.input4.setMaximum(10)
        self.label5 = QLabel("nbins")
        self.input5 = QLineEdit(str(nbins))
        self.input5.setValidator(QIntValidator(0, 1024))
        self.label6 = QLabel("max_num_iter")
        self.input6 = QLineEdit(str(max_num_iter))
        self.input6.setValidator(QIntValidator(1, 100))
        self.label7 = QLabel("min_size_factor") 
        self.input7 = QDoubleSpinBox()
        self.input7.setValue(min_size_factor)
        self.input7.setMaximum(100)
        self.label8 = QLabel("max_size_factor") 
        self.input8 = QDoubleSpinBox()
        self.input8.setValue(max_size_factor)
        self.input8.setMaximum(100)
        self.label9 = QLabel("cumulative sum multiplicator")
        self.input9 = QDoubleSpinBox()
        self.input9.setValue(multiplicator)
        self.input9.setMaximum(3)
        self.button = QPushButton("Ok")
        QBtn = QDialogButtonBox.Yes | QDialogButtonBox.No
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layoutLabel1 = QHBoxLayout()
        layoutLabel1.addWidget(self.labelSuperpixel)
        layoutLabel2 = QHBoxLayout()
        layoutLabel2.addWidget(self.labelClahe)
        layoutLabel3 = QHBoxLayout()
        layoutLabel3.addWidget(self.labelSkin)
        layout1 = QHBoxLayout()
        layout1.addWidget(self.label1)
        layout1.addWidget(self.input1)
        layout2 = QHBoxLayout()
        layout2.addWidget(self.label2)
        layout2.addWidget(self.input2)
        layout3 = QHBoxLayout()
        layout3.addWidget(self.label3)
        layout3.addWidget(self.input3)
        layout4 = QHBoxLayout()
        layout4.addWidget(self.label4)
        layout4.addWidget(self.input4)
        layout5 = QHBoxLayout()
        layout5.addWidget(self.label5)
        layout5.addWidget(self.input5)
        layout6 = QHBoxLayout()
        layout6.addWidget(self.label6)
        layout6.addWidget(self.input6)
        layout7 = QHBoxLayout()
        layout7.addWidget(self.label7)
        layout7.addWidget(self.input7)
        layout8 = QHBoxLayout()
        layout8.addWidget(self.label8)
        layout8.addWidget(self.input8)
        layout9 = QHBoxLayout()
        layout9.addWidget(self.label9)
        layout9.addWidget(self.input9)
        layout = QVBoxLayout()
        layout.addLayout(layoutLabel1)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(layout6)
        layout.addLayout(layout7)
        layout.addLayout(layout8)
        layout.addLayout(layoutLabel2)
        layout.addLayout(layout4)
        layout.addLayout(layout5)
        layout.addLayout(layoutLabel3)
        layout.addLayout(layout9)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
    def accept(self):
        global numSegments
        global sigma_slic
        global compactness
        global clip_limit
        global nbins
        global max_num_iter
        global min_size_factor
        global max_size_factor
        global multiplicator
        numSegments = int(self.input1.text())
        clip_limit = float(self.input4.text().replace(",", "."))
        sigma_slic = int(self.input3.text())
        compactness = float(self.input2.text().replace(",", "."))
        nbins = int(self.input5.text())
        max_num_iter = int(self.input6.text())
        min_size_factor = float(self.input7.text().replace(",", "."))
        max_size_factor = float(self.input8.text().replace(",", "."))
        multiplicator = float(self.input9.text().replace(",", "."))
        self.close()
# Class of the toolbar of the ploted image
class MplToolbar(NavigationToolbar2QT):
    def __init__(self, canvas_, parent_, plot=int):
        backend.figureoptions = None
        
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            ('Port', 'Back to the previous paint', "back", 'back_paint'),
            ('Clear', 'Undo an especific paint', path.realpath(path.curdir)+"/trash", 'change_undo'),
            ('Save', 'Save the current image', 'filesave', 'save_mask'),
            )
        NavigationToolbar2QT.__init__(self, canvas_, parent_)
        self._actions['change_undo'].setCheckable(True)
        self.undo = False
        self.plot = plot
    def _update_buttons_checked(self):
        if 'change_undo' in self._actions:
            self._actions['change_undo'].setChecked(self.undo)
        if 'pan' in self._actions:
            self._actions['pan'].setChecked(self.mode.name == 'PAN')
        if 'zoom' in self._actions:
            self._actions['zoom'].setChecked(self.mode.name == 'ZOOM')
    def change_undo(self):
        global undo
        self.undo = not self.undo
        if(self.undo):
            if(self.plot == 1 and undo == 0):
                undo = 1
            elif(self.plot == 2 and undo == 0):
                undo = 2
            else:
                undo = 3
        else:
            if(self.plot == 1 and undo == 1):
                undo = 0
            elif(self.plot == 2 and undo == 2):
                undo = 0
            elif(self.plot == 1 and undo == 3):
                undo = 2
            else:
                undo = 1
        if self.mode == _Mode.CLEAR:
            self.mode = _Mode.NONE
            self.canvas.widgetlock.release(self)
        else:
            self.mode = _Mode.CLEAR
            self.canvas.widgetlock(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self.mode._navigate_mode)
        self.set_message(self.mode)
        _ZoomInfo = namedtuple("_ZoomInfo", "direction start_xy axes cid cbar")
        self._update_buttons_checked()
    # Function to save the mask to png
    def save_mask(self):
        global segmentedMask
        global saveDir
        informacoesLista = []
        for i in range(informacoes["colors"].__len__()):
            informacoesLista.append([
                informacoes["colors"][i][0],
                informacoes["colors"][i][1],
                informacoes["colors"][i][2],
                i+1,
                informacoes["tissue"][i]

            ])
        # Prevent the error throwed by convert a empty array to an array
        if(not np.array_equal(segmentedMask, [])):
                a = QDir()
                if(path.exists("./defaultMaskDir.txt")):
                    f = open("./defaultMaskDir.txt")
                    f.close()
                    a.setPath(saveDir)
                else:
                    a = QDir.setPath(QDir.currentPath())
                    QFileDialog.getSaveFileUrl
                suggestedName = path.basename(fileName_global).split(".")[0]
                suggestedName = suggestedName + ".csv"
                filePath, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                            f"{a.path()}/{suggestedName}", filter="csv(*.csv)")
                if(filePath != ""):
                    np.savetxt(filePath, segmentedMask, fmt='%d', delimiter=',')  
                    f = open(filePath, "ab")
                    np.savetxt(f, np.array(informacoesLista), fmt='%d', newline=' ', delimiter=',')
                    f.write(b"\n")
                    np.savetxt(f, [np.count_nonzero(ConvertToUint8(select_RoI(dicom2array(pydicom.dcmread(fileName_global, force=True)))))], fmt='%d', delimiter=',')
                    f.close()
    # Rollbacks a state of the paint, copying the saved mask to the mask3d
    # deleting the copied and updating the view to the new mask with rollback
    def back_paint(self):
        global previous_paints 
        global mask3d
        global previous_segments
        global segmentedMask
        global segments_global
        # Checks if have backups of masks 3d to rollback
        if(previous_paints.__len__() >= 1):  
            # Copy the backup mask to the mask3d variable
            mask3d = copy.deepcopy(previous_paints[(previous_paints.__len__()-1)])
            # Delete the rollbacked mask
            previous_paints.__delitem__(previous_paints.__len__() -1)
            lastIndex = previous_segments["superpixel"].__len__()-1
            segmentedMask[segments_global == previous_segments["superpixel"][lastIndex]] = previous_segments["previous_identifier"][lastIndex]
            previous_segments["superpixel"].__delitem__(lastIndex)
            previous_segments["previous_identifier"].__delitem__(lastIndex)
            # Update the view
            if(np.array_equal(segments_global, []) and not np.array_equal(mask3d, [])):
                imageViewer.plotsuperpixelmask.showSavedMask()
            else:
                imageViewer.plotsuperpixelmask.UpdateView()

# Class that shows the painted image
class PlotSuperPixelMask(QWidget):
    def __init__(self):
        super().__init__()
        self.view = FigureCanvas()
        self.axes = self.view.figure.subplots()
        self.axes.set_title("Máscara/SuperPixel")
        # Includes the toolbar
        self.toolbar = MplToolbar(self.view, self, 1)
        # Create the event associated with a function on click
        self.view.mpl_connect('button_press_event', self.callMouseEvent)
        self.im = ""
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.toolbar)
        vlayout.addWidget(self.view)
        self.setLayout(vlayout) 
    # Update the view, displaying the mask3d(if modified, shows the new mask)
    def callMouseEvent(self, event):
        global currentPlot
        currentPlot = 0
        mouse_event(event, 1)
    def UpdateView(self):
        global mask3d
        global masks_empty
        global dicom_image_array
        global segments_global
        global selected_hu
        if (not masks_empty):
            if(self.im == ""):
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                if show_superpixel and not np.array_equal(segments_global, []):
                    self.im = self.axes.imshow(mark_boundaries(mask3d, segments_global*selected_hu))
                else:
                    self.im = self.axes.imshow(mask3d)
                self.view.draw()
            else:
                self.im.set_clim([0, 255])
                if show_superpixel and not np.array_equal(segments_global, []):
                    self.im.set_data(mark_boundaries(mask3d, segments_global*selected_hu))
                else:
                    self.im.set_data(mask3d)
                self.view.draw()
        else:
            if(self.im == ""):
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                self.im = self.axes.imshow(dicom_image_array, cmap='gray')
                self.view.draw()
            else:
                self.im.set_data(dicom_image_array)
                self.im.set_clim([dicom_image_array.min(), dicom_image_array.max()])
                self.view.draw()
    def showSavedMask(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        self.im = self.axes.imshow(mask3d)
        self.view.draw()
    # Self explanatory
    def ClearView(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
    # Apply the superpixel segmentation to the current dicom image array
    def SuperPixel(self):
        global dicom_image_array
        global fileName_global
        global segments_global
        global superpixel_auth
        global numSegments
        global mask3d
        global sigma_slic
        global compactness
        global max_num_iter
        global min_size_factor
        global max_size_factor
        global selected_hu
        # apply SLIC and extract (approximately) the supplied number of segments
        segments_global = slic(dicom_image_array, n_segments=numSegments, sigma=sigma_slic, \
                        channel_axis=None, compactness=compactness, start_label=1, max_num_iter=max_num_iter, min_size_factor=min_size_factor, max_size_factor=max_size_factor)
        
        segments_global[dicom_image_array < 20] = 0
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        if(not np.array_equal(mask3d, [])):
                self.im = self.axes.imshow(mark_boundaries(mask3d, segments_global*selected_hu))
        else:
                self.im = self.axes.imshow(mark_boundaries(dicom_image_array/255, segments_global*selected_hu), cmap='gray')
        self.view.draw()
        
        superpixel_auth = True


# Class that create the Pallete of collors to choose for paint
class QPaletteButton(QPushButton):

    def __init__(self, color):
        super().__init__()
        self.setFixedSize(QtCore.QSize(24,24))
        self.color = color
        self.setStyleSheet("background-color: %s;" % color)

class PlotWidgetModify(QWidget):
    # Very similar with 'PlotSuperpixelMask' class
    def __init__(self):
        super().__init__()
        self.segments =[]
        self.view = FigureCanvas()
        self.axes = self.view.figure.subplots()
        self.axes.set_title("Imagem Conferência")
        self.toolbar = MplToolbar(self.view, self, 2)
        self.view.mpl_connect('button_press_event', self.callMouseEvent)
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.toolbar)
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

        # self.on_change()
    def callMouseEvent(self, event):
        global currentPlot
        currentPlot = 1
        mouse_event(event, 2)
    # Self explanatory
    def ChangeSuperpixelAuth(self):
        global superpixel_auth
        superpixel_auth = False
    
    #  Apply the CLAHE method, that makes the tomography clearer
    def HistMethodClahe(self):
        global dicom_image_array
        global fileName_global
        global superpixel_auth
        # Just executes the method if exists an opened image
        if fileName_global != '':
            # Method that makes the CLAHE
            global clip_limit
            global nbins
            dicom_image_array = (exposure.equalize_adapthist(dicom_image_array/255, clip_limit=clip_limit, nbins=nbins))
            if(dicom_image_array.max()<=1):
                dicom_image_array[:,:] = (dicom_image_array[:,:]*255).astype('uint8')
            self.axes.clear()
            self.axes.set_title("Imagem Conferência")
            self.axes.imshow(dicom_image_array, cmap='gray')
            self.view.draw()
            superpixel_auth = False
    
    # Refresh the dicom image array
    def on_change(self):
        self.ChangeSuperpixelAuth()
        global dicom_image_array
        global fileName_global
        dicom_image_array = ConvertToUint8(dicom_image_array)
        """ Update the plot with the current input values """
        # if fileName_global != '': 
        #     self.dicom_image = dicom2array(pydicom.dcmread(fileName_global , force = True))
        self.axes.clear()
        self.axes.set_title("Imagem Conferência")
        if fileName_global != '':
            self.axes.imshow(dicom_image_array, cmap='gray')
            self.view.draw()
    # Reset the dicom image array
    def ResetDicom(self):
        self.ChangeSuperpixelAuth()
        global dicom_image_array
        global fileName_global
        global superpixel_auth
        if fileName_global != '':
            # Read the dicom image again
            dicom_image_array = dicom2array(pydicom.dcmread(fileName_global, force=True))
            # Convert to uint8 to display again
            dicom_image_array = ConvertToUint8(dicom_image_array)
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(dicom_image_array, cmap='gray')
        self.view.draw()
        
        superpixel_auth = False

    # Apply the delete objects method(removes unwanted objects)
    def DeleteObjects(self):
        """This method reset the dicom image, reading the original image again.
        So, the CLAHE method needs to be applied after this method."""
        self.ChangeSuperpixelAuth()
        global dicom_image_array
        global fileName_global
        global superpixel_auth
        if fileName_global != '':
            dicom_image_array = dicom2array(pydicom.dcmread(fileName_global, force=True))
            # The function that makes the method
            dicom_image_array = select_RoI(dicom_image_array)           
            dicom_image_array = ConvertToUint8(dicom_image_array)

        self.axes.imshow(dicom_image_array, cmap='gray')
        self.view.draw()
        self.axes.set_title("Imagem Conferência")
        superpixel_auth = False
    def DeleteSkin(self):
        """This method reset the dicom image, reading the original image again.
        So, the CLAHE method needs to be applied after this method."""
        self.ChangeSuperpixelAuth()
        global dicom_image_array
        global fileName_global
        global superpixel_auth
        global multiplicator
        if fileName_global != '':
            dicom_image_array = dicom2array(pydicom.dcmread(fileName_global, force=True))
            # The function that makes the method
            dicom_image_array = removeSkinAndObjects(dicom_image_array, multiplicator)           
            dicom_image_array = ConvertToUint8(dicom_image_array)
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(dicom_image_array, cmap='gray')
        self.view.draw()
        superpixel_auth = False

# Class that manage the layout of the window.
class ImageViewer(QMainWindow):
    def __init__(self):
        super(ImageViewer, self).__init__()

        self.bar = self.addToolBar("Menu")
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.color_action = QAction(self)
        self.color_action.triggered.connect(self.on_color_clicked)
        self.bar.addAction(self.color_action)
        # Put yellow as default color to paint
        self.set_color(Qt.yellow)
        self.bar.addWidget(QLabel(" Current tissue: "))
        self.current_tissue = QLabel("")
        self.bar.addWidget(self.current_tissue)
        self.current_tissue.setText("None")
        # self.plotwidget_original = PlotWidgetOriginal()

        # Store the instanced object of the widget modified class
        self.plotwidget_modify = PlotWidgetModify()
        
        # Store the instanced object of the painted mask class
        self.plotsuperpixelmask = PlotSuperPixelMask()   
        self.layout = QHBoxLayout()
        layout2 = QVBoxLayout()
        layout3 = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        # layout2.addWidget(self.plotwidget_original)

        # Shows the painted mask instanced class in the app layout
        layout2.addWidget(self.plotsuperpixelmask)

        self.layout.addLayout(layout2)

        # Shows the widget modified class in the app layout
        layout3.addWidget(self.plotwidget_modify)

        self.layout.addLayout(layout3)
        # self.layout.addWidget(self.imageLabel)

        palette = QHBoxLayout()
        self.add_palette_buttons(palette)

        # Shows the main layout, that contains the other 2(superpixel 
        # and modified)
        main_widget = QWidget()
        main_widget.setLayout(self.layout)
        self.setCentralWidget(main_widget)

        ###################################
        # palette = main_widget.QHBoxLayout()
        # self.add_palette_buttons(palette)
        # self.layout.addLayout(palette)
        
        self.createActions()
        self.createMenus()
        self.getDirsPath()
        # Create the size of the layout
        # self.setGeometry(250, 100, 1000, 600)
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("./icon.png"))

    @Slot()
    def on_color_clicked(self, layout):
        """When a color is changed, this function is activated and 
        changes the 'colorvec' global variable that stores the current
        color for paint"""
        global informacoes
        global currentTissue
        global masks
        global segmentedMask
        global selected_hu
        global fat_hu
        global muscle_hu
        color = QColorDialog.getColor(Qt.black, self)
        qcolor = QColor(color)
        if qcolor.red() != 0 or qcolor.green() != 0 or qcolor.blue() != 0:
            # Put the RGB colors in the 'colorvec' global variable
            selectedColor= np.array([qcolor.red(), qcolor.green(), qcolor.blue()])
            verif = False
            index = 0
            for i in range(informacoes["colors"].__len__()):
                if(np.array_equal(informacoes["colors"][i], selectedColor)):
                    tissue = informacoes["tissue"][i]
                    for key in dictTissues.keys():
                        if(dictTissues[key] == tissue):
                            self.current_tissue.setText(key)
                    verif = True
                    index = i
            if(verif):
                currentTissue = index + 1
                self.set_color(color)
            else:
                item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                if(ok):
                    self.set_color(color)
                    if(informacoes["tissue"].count(dictTissues[item])>0):
                        self.current_tissue.setText(item)
                        currentTissue = informacoes["tissue"].index(dictTissues[item]) + 1
                        informacoes["colors"][currentTissue-1] = selectedColor
                        if(not np.array_equal(mask3d, [])):
                            masks = np.zeros_like(dicom_image_array, dtype="bool")
                            masks[segmentedMask == currentTissue] = 1
                            # show the masked region
                            ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 

                            mask3d[:,:,0] = informacoes['colors'][currentTissue -1][0] * masks + mask3d[:,:,0]*(~masks).astype('uint8')
                            mask3d[:,:,1] = informacoes['colors'][currentTissue -1][1] * masks + mask3d[:,:,1]*(~masks).astype('uint8')
                            mask3d[:,:,2] = informacoes['colors'][currentTissue -1][2] * masks + mask3d[:,:,2]*(~masks).astype('uint8')
                            self.plotsuperpixelmask.UpdateView()
                            
                    else:
                        size = informacoes["colors"].__len__()
                        informacoes["colors"].append(selectedColor)
                        informacoes["identifier"].append(size+1)
                        informacoes["tissue"].append(dictTissues[item])            
                        currentTissue = size+1  
                        self.current_tissue.setText(item)
            if informacoes["tissue"][currentTissue - 1] in [1, 2, 3]:
                selected_hu = fat_hu
            elif informacoes["tissue"][currentTissue - 1] in [5]:
                selected_hu = muscle_hu
            self.plotsuperpixelmask.UpdateView()

    def set_color(self, color: QColor = Qt.black):
        """ Changes the color icon for the selected """
        pix_icon = QPixmap(20, 20)
        pix_icon.fill(color)

        self.color_action.setIcon(QIcon(pix_icon))
        # self.imageLabel.set_pen_color(color)
        # self.color_action.setText(QColor(color).name())

    def add_palette_buttons(self, layout):
        for c in COLORS:
            b = QPaletteButton(c)
            b.pressed.connect(lambda c=c: self.canvas.set_pen_color(c))
    def recoveryMask3d(self):
        global mask3d
        global informacoes
        global segmentedMask
        global masks
        global fileName_global
        masks = np.zeros_like(segmentedMask, dtype="bool")
        
        mask3d = np.zeros((segmentedMask.shape[0],segmentedMask.shape[1],3), dtype = "uint8")
        if(fileName_global.split(".")[1] == "dcm"):
            mask3d[:,:,0] = dicom_image_array 
            mask3d[:,:,1] = dicom_image_array 
            mask3d[:,:,2] = dicom_image_array
        for i in range(informacoes["tissue"].__len__()):
            masks = np.zeros_like(segmentedMask, dtype="bool")
            masks[segmentedMask == informacoes["identifier"][i]] = 1
            mask3d[:,:,0] = informacoes['colors'][i][0] * masks + mask3d[:,:,0]*(~masks).astype('uint8')
            mask3d[:,:,1] = informacoes['colors'][i][1] * masks + mask3d[:,:,1]*(~masks).astype('uint8')
            mask3d[:,:,2] = informacoes['colors'][i][2] * masks + mask3d[:,:,2]*(~masks).astype('uint8')
        self.plotsuperpixelmask.showSavedMask()
        
        
    def open(self):
        """Open the interface to choose the file to display in the app"""
        global fileName_global
        global dicom_image_array
        global mask3d
        global masks_empty
        global currentTissue
        global informacoes
        global dictTissues
        global segmentedMask
        global csvFlag
        global segments_global
        global superpixel_auth
        global previous_paints
        global previous_segments
        global area
        global fat_hu
        global muscle_hu
        global selected_hu
        previous_segments = {"superpixel":[], "previous_identifier":[]}
        previous_paints = []
        fileName = self.pathFile()
        if(fileName):
            superpixel_auth = False
            fileName_global = fileName
            if(fileName_global.split(".")[1] == "csv"):
                csvFlag = True
                file = open(fileName_global)
                lines = file.readlines()
                area = int(lines[lines.__len__()-1].strip())
                informacoesStr = lines[lines.__len__()-2].split(" ")[:-1]
                for i in range(informacoesStr.__len__()):
                    informacoesStr[i] = informacoesStr[i].split(",")
                informacoesInt = np.array(informacoesStr, dtype=int)
                informacoes = {"colors":[], "identifier":[], "tissue":[]}
                for i in range(informacoesInt.__len__()):
                    informacoes["colors"].append(np.array([informacoesInt[i][0], informacoesInt[i][1], informacoesInt[i][2]]))
                    informacoes["identifier"].append(informacoesInt[i][3])
                    informacoes["tissue"].append(informacoesInt[i][4])
                tempMask = []
                for i in range(lines.__len__()-2):
                    tempMask.append(np.array(lines[i].split(","), dtype=int))
                segmentedMask = np.array(tempMask, dtype=int)
                self.recoveryMask3d()
                file.close()
                self.plotwidget_modify.axes.clear()
                self.plotwidget_modify.axes.set_title("Imagem Conferência")
                self.plotwidget_modify.view.draw()
                dicom_image_array = []
            else:
                dicom_image_array = dicom2array(pydicom.dcmread(fileName_global, force=True))
                
                # Obter os valores na leitura de imagem no diretório
                muscle_hu = tissue_segmentation(select_RoI(dicom_image_array), "muscle")
                fat_hu = tissue_segmentation(select_RoI(dicom_image_array), "fat")
                selected_hu = np.ones((dicom_image_array.shape))
                
                dicom_image_array =  ConvertToUint8(dicom_image_array)
                area = np.count_nonzero(ConvertToUint8(select_RoI(dicom2array(pydicom.dcmread(fileName_global, force=True)))))
                # self.plotwidget_original.on_change()
                self.plotwidget_modify.on_change()
                ok = 0
                if(csvFlag):
                    confirmDialog = CustomDialog()
                    ok = confirmDialog.show()
                if(ok):  
                    currentTissue = 1
                    self.set_color(QColor(informacoes["colors"][0][0], informacoes["colors"][0][1], informacoes["colors"][0][2]))
                    segments_global = []
                    self.recoveryMask3d()
                    masks_empty = False
                else:
                    mask3d = []
                    self.plotsuperpixelmask.im = ""
                    masks_empty = True
                    currentTissue = 0
                    segmentedMask = []
                    segments_global = []
                    informacoes = {"colors":[], "identifier":[], "tissue":[]}
                    item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                    while not ok:
                        item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                    informacoes["colors"].append(np.array([255, 255, 0]))
                    informacoes["identifier"].append(1)
                    informacoes["tissue"].append(dictTissues[item]) 
                    currentTissue = 1
                    self.current_tissue.setText(item)
                    self.set_color(Qt.yellow)
                    if informacoes["tissue"][currentTissue - 1] in [1, 2, 3]:
                        selected_hu = fat_hu
                    elif informacoes["tissue"][currentTissue - 1] in [5]:
                        selected_hu = muscle_hu
                    imageViewer.plotsuperpixelmask.UpdateView()
                csvFlag = False
    def pathFile(self):
        """Get the path of the selected file"""
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File",
                                                         openDir, filter="DICOM (*.dcm *.);;csv(*.csv)")
        return fileName


    #Follow methods are self explanatory
    def HistMethodCLAHE(self):
        global dicom_image_array
        global segments_global
        global mask3d
        global radio_density_check_enabled
        self.resetToggleState()

        if not np.array_equal(dicom_image_array, []):
            if(masks_empty == True):
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.HistMethodClahe()
            if(np.array_equal(segments_global, []) and not np.array_equal(mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            elif(not np.array_equal(mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            else:
                self.plotsuperpixelmask.UpdateView()  
    
    def SuperPixel(self):
        global dicom_image_array, toggle_available, radio_density_check_enabled
        # self.plotwidget_original.SuperPixel()
        self.resetToggleState()
        if not np.array_equal(dicom_image_array, []):
            self.plotsuperpixelmask.SuperPixel()
            toggle_available = True

    def toggleRadioDensityCheck(self):
        global dicom_image_array, radio_density_check_enabled
        if not np.array_equal(dicom_image_array, []):
            # self.plotsuperpixelmask.SuperPixel()
            radio_density_check_enabled = not radio_density_check_enabled

    def OriginalImage(self):
        global fileName_global
        global segments_global
        global mask3d
        global radio_density_check_enabled
        # self.plotwidget_original.ResetDicom()
        self.resetToggleState()

        if fileName_global != '':
            if not fileName_global.split(".")[1] == "csv":
                self.plotwidget_modify.ResetDicom()
                if(masks_empty):
                    self.plotsuperpixelmask.im = ""
                if(np.array_equal(segments_global, []) and not np.array_equal(mask3d, [])):
                    self.plotsuperpixelmask.showSavedMask()
                elif(not np.array_equal(mask3d, [])):
                    self.recoveryMask3d()
                    self.plotsuperpixelmask.showSavedMask()
                else:
                    self.plotsuperpixelmask.UpdateView()  
    def RemoveObjects(self):
        global dicom_image_array
        global segments_global
        global mask3d
        global radio_density_check_enabled
        # self.plotwidget_original.DeleteObjects()
        self.resetToggleState()

        if not np.array_equal(dicom_image_array, []):
            if(masks_empty == True):
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.DeleteObjects()
            if(np.array_equal(segments_global, []) and not np.array_equal(mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            elif(not np.array_equal(mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            else:
                self.plotsuperpixelmask.UpdateView()  
    def RemoveSkin(self):
            global dicom_image_array
            global segments_global
            global mask3d
            global radio_density_check_enabled
            # self.plotwidget_original.DeleteObjects()
            self.resetToggleState()

            if not np.array_equal(dicom_image_array, []):
                if(masks_empty == True):
                    self.plotsuperpixelmask.im = ""
                self.plotwidget_modify.DeleteSkin()
                if(np.array_equal(segments_global, []) and not np.array_equal(mask3d, [])):
                    self.recoveryMask3d()
                    self.plotsuperpixelmask.showSavedMask()
                elif(not np.array_equal(mask3d, [])):
                    self.recoveryMask3d()
                    self.plotsuperpixelmask.showSavedMask()
                else:
                    self.plotsuperpixelmask.UpdateView()  
    def about(self):
        QMessageBox.about(self, "LAMAC",
                          "<p>Segmentador Manual !!! </p>")

    def the_button_was_clicked(self):
        self.SuperPixel()

    def changeOptions(self):
        form = Form()
        form.exec()
    def resetMask3d(self):
        global mask3d
        global previous_paints
        global masks_empty
        if(not np.array_equal(dicom_image_array, [])):
            previous_paints = []
            mask3d = np.zeros((dicom_image_array.shape[0],dicom_image_array.shape[1],3), dtype = "uint8")
            mask3d[:,:,0] = dicom_image_array 
            mask3d[:,:,1] = dicom_image_array 
            mask3d[:,:,2] = dicom_image_array
            masks_empty = False
            previous_paints.append(copy.deepcopy(mask3d))
            imageViewer.plotsuperpixelmask.UpdateView()
    def calculatePercentages(self):
        global graph
        graph = PercentagesGraph()
        graph.calculatePercentages()
        graph.show()
    def setDefaultOpen(self):
        global openDir
        Dir = QFileDialog.getExistingDirectory(self)
        if(Dir != ""):
            openDir = Dir
            f = open("./defaultImageDir.txt", "w")
            f.write(openDir)
            f.close()
    def setDefaultSave(self):
        global saveDir
        Dir = QFileDialog.getExistingDirectory(self)
        
        if(Dir !=  ""):
            saveDir = Dir
            f = open("./defaultMaskDir.txt", "w")
            f.write(saveDir)
            f.close()
    def getDirsPath(self):
        global saveDir
        global openDir
        if(path.exists("./defaultImageDir.txt")):
            f = open("./defaultImageDir.txt")
            openDir = f.readline()
            f.close()
        if(path.exists("./defaultMaskDir.txt")):
            f = open("./defaultMaskDir.txt")
            saveDir = f.readline()
            f.close()
    def alternar(self):
        global numSegments
        if(numSegments == 2000):
            numSegments = 500
        elif(numSegments == 500):
            numSegments = 5000
        else:
            numSegments = 2000

    def toggleSuperPixelView(self):
        global show_superpixel, superpixel_auth, segments_global, toggle_available

        if not toggle_available:
            QMessageBox.warning(self, "Aviso", "Você precisa aplicar o SuperPixel antes de usar o Toggle.")
            return
        
        superpixel_auth = not superpixel_auth
        show_superpixel = not show_superpixel
        print(f"SuperPíxel {'visível' if show_superpixel else 'oculto'}")
        self.plotsuperpixelmask.UpdateView()

    def resetToggleState(self):
        global show_superpixel, superpixel_auth, toggle_available
        show_superpixel = True
        superpixel_auth = False
        toggle_available = False

    def createActions(self):
        """Create the actions to put in menu options"""
        self.openAct = QtGui.QAction("&Open...", self, shortcut="Ctrl+O",
                                     triggered=self.open)
        self.exitAct = QtGui.QAction("E&xit", self, shortcut="Ctrl+Q",
                                     triggered=self.close)
        self.HistMethodCLAHEAct = QtGui.QAction("&Hist CLAHE", self, shortcut="Ctrl+C",
                                                triggered=self.HistMethodCLAHE)
        self.SuperPixelAct = QtGui.QAction("&SuperPixel", self,  shortcut="Ctrl+Shift+S",
                                           triggered=self.SuperPixel)
        self.toggleRadioDensityCheckAct = QtGui.QAction("&Toggle RD check", self, shortcut="Ctrl+Shift+D", 
                                             triggered=self.toggleRadioDensityCheck)
        self.OriginalImageAct = QtGui.QAction("&Original Image", self,
                                              triggered=self.OriginalImage)
        self.RemoveObjectsAct = QtGui.QAction("&Remove Objects", self,  shortcut="Ctrl+R",
                                              triggered=self.RemoveObjects)
        self.RemoveSkinAndObjectsAct = QtGui.QAction("&Remove Skin and Objects", self,  shortcut="Ctrl+Shift+R",
                                              triggered=self.RemoveSkin)
        
        self.aboutAct = QtGui.QAction("&About", self, triggered=self.about)

        self.aboutQtAct = QtGui.QAction("About &Qt", self,
                                        triggered=qApp.aboutQt)
        self.saveAct = QtGui.QAction("&Save", self, shortcut="Ctrl+S",
                                     triggered=self.plotsuperpixelmask.toolbar.save_mask)
        self.backPaintAct = QtGui.QAction("&Back", self, shortcut="Ctrl+Z",
                                     triggered=self.plotsuperpixelmask.toolbar.back_paint)
        self.toggleSuperPixelAct = QtGui.QAction("&Toggle SuperPixel View", self, shortcut="Ctrl+T",
                                         triggered=self.toggleSuperPixelView)
        self.changeOptionsAct = QtGui.QAction("&Change Options", self,
                                     triggered=self.changeOptions)
        self.calculatePercentagesAct = QtGui.QAction("&Calculate Percentages", self,
                                     triggered=self.calculatePercentages)
        self.setDefaultOpenDirAct = QtGui.QAction("&Default Open Directory", self,
                                     triggered=self.setDefaultOpen)
        self.setDefaultSaveDirAct = QtGui.QAction("&Default Save Directory", self,
                                     triggered=self.setDefaultSave)
        self.alternarAct = QtGui.QAction("&Alternar", self, shortcut="Ctrl+F",
                                     triggered=self.alternar)
    def createMenus(self):
        """Put the created actions in a menu"""
        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addAction(self.exitAct)

        self.viewMenu = QMenu("&View", self)
        self.viewMenu.addAction(self.SuperPixelAct)
        self.viewMenu.addAction(self.toggleRadioDensityCheckAct)
        self.viewMenu.addAction(self.toggleSuperPixelAct)
        self.viewMenu.addAction(self.HistMethodCLAHEAct)
        self.viewMenu.addAction(self.OriginalImageAct)
        self.viewMenu.addAction(self.RemoveObjectsAct)
        self.viewMenu.addAction(self.RemoveSkinAndObjectsAct)
        self.viewMenu.addAction(self.backPaintAct)
        self.viewMenu.addAction(self.calculatePercentagesAct)
        self.optionsMenu = QMenu("&Options", self)
        self.optionsMenu.addAction(self.changeOptionsAct)
        self.optionsMenu.addAction(self.setDefaultOpenDirAct)
        self.optionsMenu.addAction(self.setDefaultSaveDirAct)
        self.optionsMenu.addAction(self.alternarAct)
        self.helpMenu = QMenu("&Help", self)
        self.helpMenu.addAction(self.aboutAct)
        self.helpMenu.addAction(self.aboutQtAct)

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.optionsMenu)
        self.menuBar().addMenu(self.helpMenu)
        
if __name__ == '__main__':
    import sys

    # Instances the app and shows the main class
    app = QApplication(sys.argv)
    imageViewer = ImageViewer()
    imageViewer.show()
    sys.exit(app.exec())