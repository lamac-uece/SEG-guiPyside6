from collections import namedtuple
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import cv2 as cv2
from matplotlib import pyplot as plt
import numpy as np
from skimage import exposure
import skimage.filters.edges
# import pydicom.encoders.gdcm
# import gdcm
# from libjpeg import decode_pixel_data
# import pydicom.encoders.pylibjpeg
import pydicom.pixel_data_handlers.pylibjpeg_handler
from skimage.segmentation import mark_boundaries, slic
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.backends.backend_qt5 as backend
from src.services.dicom_service import dicom2array
from src.services.image_processing import (
    select_RoI,
    apply_clahe,
    compute_superpixels,
    removeSkinAndObjects,
)
from src.services.mask_io import load_mask, save_mask
from src.utils.image_utils import (
    ConvertToUint8,
    tissue_segmentation,
    bitwise_minus,
    remove_small_CCs,
    find_extreme_points,
    compose_muscle_mask,
)
from src.models.tissue_config import materials, colors, dictTissues
from src.models.segmentation_state import SegmentationState
from functions import _Mode
from functions import CustomDialog
# from src.views.dialogs import CustomDialog
import copy
from PIL import Image
from os import path
from scipy.ndimage import binary_fill_holes
state = SegmentationState()

# Click event for paint superpixel
def mouse_event(event, plot=int):
    if ((event.xdata != None or event.ydata != None) 
    and ((event.xdata > 1 and event.ydata >1)) 
    and (state.superpixel_auth == True) 
    and (
        (
        (str(imageViewer.plotsuperpixelmask.toolbar._actions["zoom"]).__contains__("checked=false"))
        and (str(imageViewer.plotsuperpixelmask.toolbar._actions["pan"]).__contains__("checked=false"))
        and state.current_plot == 0
        )
    or 
        (
        (str(imageViewer.plotwidget_modify.toolbar._actions["zoom"]).__contains__("checked=false"))
        and (str(imageViewer.plotwidget_modify.toolbar._actions["pan"]).__contains__("checked=false"))
        and state.current_plot == 1
        ))
    ): 
        paintSuperPixel(event.xdata,event.ydata,state.segments_global, plot)

def paintSuperPixel(x,y,segments, plot=int):
    if(segments[int(y)][int(x)] == 0):
        return
    if(np.array_equal(state.segmented_mask, [])):
        state.segmented_mask = np.zeros_like(state.dicom_image_array, dtype="uint8")
    if(state.masks_empty):
        # Creates a new 3d mask with the shape of the dicom image array
        state.mask3d = np.zeros(
            (state.dicom_image_array.shape[0],
             state.dicom_image_array.shape[1],3), 
             dtype = "uint8"
        )
        state.mask3d[:,:,0] = state.dicom_image_array 
        state.mask3d[:,:,1] = state.dicom_image_array 
        state.mask3d[:,:,2] = state.dicom_image_array
        state.masks_empty = False
    
    state.masks = np.zeros_like(state.dicom_image_array, dtype="bool")
    # Store a copy of mask3d for rollback
    state.previous_paints.append(copy.deepcopy(state.mask3d))
    segment_id = segments[int(y)][int(x)]

    state.previous_segments["superpixel"].append(segment_id)
    state.previous_segments["previous_identifier"].append(state.segmented_mask[int(y)][int(x)])
    
    # Verify if exists more than 10 copies, for delete the older
    if(state.previous_paints.__len__() == 11):
            state.previous_paints.__delitem__(0)
            state.previous_segments["superpixel"].__delitem__(0)
            state.previous_segments["previous_identifier"].__delitem__(0)

    if((plot == 1 and state.undo == 1) or(plot == 2 and state.undo == 2) or state.undo == 3):
        state.masks = np.ones_like(state.dicom_image_array, dtype="bool")
        state.segmented_mask[segments==segments[int(y)][int(x)]] = 0       
        # Verify what segments of segments global are equals to 
        # the clicked segment to change this masks elements to 1, 
        # instead of false
        state.masks[segments == segments[int(y)][int(x)]] = 0
        # show the masked region
        ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 

        state.mask3d[:,:,0] = state.dicom_image_array  * (~state.masks).astype('uint8') + state.mask3d[:,:,0]*(state.masks).astype('uint8')
        state.mask3d[:,:,1] = state.dicom_image_array  * (~state.masks).astype('uint8') + state.mask3d[:,:,1]*(state.masks).astype('uint8')
        state.mask3d[:,:,2] = state.dicom_image_array  * (~state.masks).astype('uint8') + state.mask3d[:,:,2]*(state.masks).astype('uint8')
    else:
        hu_mask = np.ones_like(state.dicom_image_array, dtype=bool)        
        if state.radio_density_check_enabled :
            tissue = state.informacoes["tissue"][state.current_tissue - 1]
            if tissue in [1, 2, 3] :
                hu_mask = hu_mask * state.fat_hu
            elif tissue in [5]:
                hu_mask = hu_mask * state.muscle_hu
                
        state.segmented_mask[(hu_mask * segments)==segments[int(y)][int(x)]] = state.current_tissue            
        # Verify what segments of segments global are equals to 
        # the clicked segment to change this masks elements to 1, 
        # instead of false
        state.masks[(hu_mask * segments) == segments[int(y)][int(x)]] = 1
        # show the masked region
        ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 
        color = state.informacoes["colors"][state.current_tissue - 1]
        state.mask3d[:,:,0] = color[0] * state.masks + state.mask3d[:,:,0]*(~state.masks).astype('uint8')
        state.mask3d[:,:,1] = color[1] * state.masks + state.mask3d[:,:,1]*(~state.masks).astype('uint8')
        state.mask3d[:,:,2] = color[2] * state.masks + state.mask3d[:,:,2]*(~state.masks).astype('uint8')
        
    # Update the mask with the new rgb mask(with the new painted superpixel)
    imageViewer.plotsuperpixelmask.UpdateView()

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
        if(not (np.array_equal(state.mask3d, []) 
        or np.array_equal(state.segmented_mask, []))):
            totalpixels = state.area
            labels = []
            sizes = []
            listKeys = list(state.dictTissues.keys())
            listValues = list(state.dictTissues.values())
            for i in range(state.informacoes["tissue"].__len__()):
                tissue = state.informacoes["tissue"][i]
                identifier = state.informacoes["identifier"][i]
                labels.append(listKeys[listValues.index(tissue)])
                pixels = np.count_nonzero(state.segmented_mask == identifier)
                totalpixels = totalpixels - pixels
                sizes.append(pixels)
            sizes.append(totalpixels)
            labels.append("Unsegmented")
            sizes[:] = [100*x / sum(sizes) for x in sizes]
            colors = []
            colors[:] = [[color[0]/255, color[1]/255, color[2]/255] for color in state.informacoes["colors"]]
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
        self.setWindowTitle("Parâmetros")
        self.labelSuperpixel = QLabel("<h1>Superpixel</h1>")
        self.labelClahe = QLabel("<h1>Clahe</h1>")
        self.labelSkin = QLabel("<h1>Skin Segmentation</h1>")
        self.label1 = QLabel("Superpixels")
        self.input1 = QLineEdit(str(state.num_segments))
        self.input1.setValidator(QIntValidator(1000, 10000))
        self.label2 = QLabel("Compactness")
        self.input2 = QDoubleSpinBox()
        self.input2.setValue(state.compactness)
        self.input2.setMaximum(100)
        self.label3 = QLabel("sigma")
        self.input3 = QLineEdit(str(state.sigma_slic))
        self.input3.setValidator(QIntValidator(0, 10))
        self.label4 = QLabel("Clip limit(CLAHE)") 
        self.input4 = QDoubleSpinBox()
        self.input4.setValue(state.clip_limit)
        self.input4.setMaximum(10)
        self.label5 = QLabel("nbins")
        self.input5 = QLineEdit(str(state.nbins))
        self.input5.setValidator(QIntValidator(0, 1024))
        self.label6 = QLabel("max_num_iter")
        self.input6 = QLineEdit(str(state.max_num_iter))
        self.input6.setValidator(QIntValidator(1, 100))
        self.label7 = QLabel("min_size_factor") 
        self.input7 = QDoubleSpinBox()
        self.input7.setValue(state.min_size_factor)
        self.input7.setMaximum(100)
        self.label8 = QLabel("max_size_factor") 
        self.input8 = QDoubleSpinBox()
        self.input8.setValue(state.max_size_factor)
        self.input8.setMaximum(100)
        self.label9 = QLabel("cumulative sum multiplicator")
        self.input9 = QDoubleSpinBox()
        self.input9.setValue(state.multiplicator)
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
        state.num_segments = int(self.input1.text())
        state.clip_limit = float(self.input4.text().replace(",", "."))
        state.sigma_slic = int(self.input3.text())
        state.compactness = float(self.input2.text().replace(",", "."))
        state.nbins = int(self.input5.text())
        state.max_num_iter = int(self.input6.text())
        state.min_size_factor = float(self.input7.text().replace(",", "."))
        state.max_size_factor = float(self.input8.text().replace(",", "."))
        state.multiplicator = float(self.input9.text().replace(",", "."))
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
        state.undo = not state.undo
        if(state.undo):
            if(state.plot == 1 and state.undo == 0):
                state.undo = 1
            elif(state.plot == 2 and state.undo == 0):
                state.undo = 2
            else:
                state.undo = 3
        else:
            if(state.plot == 1 and state.undo == 1):
                state.undo = 0
            elif(state.plot == 2 and state.undo == 2):
                state.undo = 0
            elif(state.plot == 1 and state.undo == 3):
                state.undo = 2
            else:
                state.undo = 1
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
        informacoesLista = []
        for i in range(state.informacoes["colors"].__len__()):
            informacoesLista.append([
                state.informacoes["colors"][i][0],
                state.informacoes["colors"][i][1],
                state.informacoes["colors"][i][2],
                i+1,
                state.informacoes["tissue"][i]

            ])
        # Prevent the error throwed by convert a empty array to an array
        if(not np.array_equal(state.segmented_mask, [])):
                a = QDir()
                if(path.exists("./defaultMaskDir.txt")):
                    f = open("./defaultMaskDir.txt")
                    f.close()
                    a.setPath(state.save_dir)
                else:
                    a = QDir.setPath(QDir.currentPath())
                    QFileDialog.getSaveFileUrl
                suggestedName = path.basename(state.file_name_global).split(".")[0]
                suggestedName = suggestedName + ".csv"
                state.file_name, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                            f"{a.path()}/{suggestedName}", filter="csv(*.csv)")
                if(state.file_name != ""):
                    save_mask(state.file_name, state.segmented_mask, state.informacoes, state.area)
    # Rollbacks a state of the paint, copying the saved mask to the mask3d
    # deleting the copied and updating the view to the new mask with rollback
    def back_paint(self):
        # Checks if have backups of masks 3d to rollback
        if(state.previous_paints.__len__() >= 1):  
            # Copy the backup mask to the mask3d variable
            state.mask3d = copy.deepcopy(state.previous_paints[(state.previous_paints.__len__()-1)])
            # Delete the rollbacked mask
            state.previous_paints.__delitem__(state.previous_paints.__len__() -1)
            lastIndex = state.previous_segments["superpixel"].__len__()-1
            state.segmented_mask[state.segments_global == state.previous_segments["superpixel"][lastIndex]] = state.previous_segments["previous_identifier"][lastIndex]
            state.previous_segments["superpixel"].__delitem__(lastIndex)
            state.previous_segments["previous_identifier"].__delitem__(lastIndex)
            # Update the view
            if(np.array_equal(state.segments_global, []) and not np.array_equal(state.mask3d, [])):
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
        if (not state.masks_empty):
            if(self.im == ""):
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                if state.show_superpixel and not np.array_equal(state.segments_global, []):
                    self.im = self.axes.imshow(mark_boundaries(state.mask3d, state.segments_global*state.selected_hu))
                else:
                    self.im = self.axes.imshow(state.mask3d)
                self.view.draw()
            else:
                self.im.set_clim([0, 255])
                if state.show_superpixel and not np.array_equal(state.segments_global, []):
                    self.im.set_data(mark_boundaries(state.mask3d, state.segments_global*state.selected_hu))
                else:
                    self.im.set_data(state.mask3d)
                self.view.draw()
        else:
            if(self.im == ""):
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                self.im = self.axes.imshow(state.dicom_image_array, cmap='gray')
                self.view.draw()
            else:
                self.im.set_data(state.dicom_image_array)
                self.im.set_clim([state.dicom_image_array.min(), state.dicom_image_array.max()])
                self.view.draw()
    def showSavedMask(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        self.im = self.axes.imshow(state.mask3d)
        self.view.draw()
    # Self explanatory
    def ClearView(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
    # Apply the superpixel segmentation to the current dicom image array
    def SuperPixel(self):
        # apply SLIC and extract (approximately) the supplied number of segments
        state.segments_global = compute_superpixels(
            state.dicom_image_array,
            n_segments=state.num_segments,
            sigma=state.sigma_slic,
            compactness=state.compactness,
            start_label=1,
            max_num_iter=state.max_num_iter,
            min_size_factor=state.min_size_factor,
            max_size_factor=state.max_size_factor
        )
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        if(not np.array_equal(state.mask3d, [])):
                self.im = self.axes.imshow(mark_boundaries(state.mask3d, state.segments_global*state.selected_hu))
        else:
                self.im = self.axes.imshow(mark_boundaries(state.dicom_image_array/255, state.segments_global*state.selected_hu), cmap='gray')
        self.view.draw()
        
        state.superpixel_auth = True


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
        state.current_plot = 1
        mouse_event(event, 2)
    # Self explanatory
    def ChangeSuperpixelAuth(self):
        state.superpixel_auth = False

    #  Apply the CLAHE method, that makes the tomography clearer
    def HistMethodClahe(self):
        # Just executes the method if exists an opened image
        if state.file_name_global != '':
            # Method that makes the CLAHE
            state.dicom_image_array = apply_clahe(
                state.dicom_image_array,
                clip_limit=state.clip_limit,
                nbins=state.nbins
            )
            self.axes.clear()
            self.axes.set_title("Imagem Conferência")
            self.axes.imshow(state.dicom_image_array, cmap='gray')
            self.view.draw()
            state.superpixel_auth = False

    # Refresh the dicom image array
    def on_change(self):
        self.ChangeSuperpixelAuth()
        state.dicom_image_array = ConvertToUint8(state.dicom_image_array)
        """ Update the plot with the current input values """
        # if fileName_global != '': 
        #     self.dicom_image = dicom2array(pydicom.dcmread(fileName_global , force = True))
        self.axes.clear()
        self.axes.set_title("Imagem Conferência")
        if state.file_name_global != '':
            self.axes.imshow(state.dicom_image_array, cmap='gray')
            self.view.draw()
    # Reset the dicom image array
    def ResetDicom(self):
        self.ChangeSuperpixelAuth()
        if state.file_name_global != '':
            # Read the dicom image again
            state.dicom_image_array = dicom2array(pydicom.dcmread(state.file_name_global, force=True))
            # Convert to uint8 to display again
            state.dicom_image_array = ConvertToUint8(state.dicom_image_array)
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(state.dicom_image_array, cmap='gray')
        self.view.draw()
        
        state.superpixel_auth = False

    # Apply the delete objects method(removes unwanted objects)
    def DeleteObjects(self):
        """This method reset the dicom image, reading the original image again.
        So, the CLAHE method needs to be applied after this method."""
        self.ChangeSuperpixelAuth()
        if state.file_name_global != '':
            state.dicom_image_array = dicom2array(pydicom.dcmread(state.file_name_global, force=True))
            # The function that makes the method
            state.dicom_image_array = select_RoI(state.dicom_image_array)
            state.dicom_image_array = ConvertToUint8(state.dicom_image_array)

        self.axes.imshow(state.dicom_image_array, cmap='gray')
        self.view.draw()
        self.axes.set_title("Imagem Conferência")
        state.superpixel_auth = False
    def DeleteSkin(self):
        """This method reset the dicom image, reading the original image again.
        So, the CLAHE method needs to be applied after this method."""
        self.ChangeSuperpixelAuth()
        if state.file_name_global != '':
            state.dicom_image_array = dicom2array(pydicom.dcmread(state.file_name_global, force=True))
            # The function that makes the method
            state.dicom_image_array = removeSkinAndObjects(state.dicom_image_array, state.multiplicator)           
            state.dicom_image_array = ConvertToUint8(state.dicom_image_array)
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(state.dicom_image_array, cmap='gray')
        self.view.draw()
        state.superpixel_auth = False

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
        color = QColorDialog.getColor(Qt.black, self)
        qcolor = QColor(color)
        if qcolor.red() != 0 or qcolor.green() != 0 or qcolor.blue() != 0:
            # Put the RGB colors in the 'colorvec' global variable
            selectedColor= np.array([qcolor.red(), qcolor.green(), qcolor.blue()])
            verif = False
            index = 0
            for i in range(state.informacoes["colors"].__len__()):
                if(np.array_equal(state.informacoes["colors"][i], selectedColor)):
                    tissue = state.informacoes["tissue"][i]
                    for key in dictTissues.keys():
                        if(dictTissues[key] == tissue):
                            self.current_tissue.setText(key)
                    verif = True
                    index = i
            if(verif):
                state.current_tissue = index + 1
                self.set_color(color)
            else:
                item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                if(ok):
                    self.set_color(color)
                    if(state.informacoes["tissue"].count(dictTissues[item])>0):
                        self.current_tissue.setText(item)
                        state.current_tissue = state.informacoes["tissue"].index(dictTissues[item]) + 1
                        state.informacoes["colors"][state.current_tissue-1] = selectedColor
                        if(not np.array_equal(state.mask3d, [])):
                            state.masks = np.zeros_like(state.dicom_image_array, dtype="bool")
                            state.masks[state.segmented_mask == state.current_tissue] = 1
                            # show the masked region
                            ## D_I_A = ((255 * dicom_image_array) * (~masks)).astype('uint8') 

                            state.mask3d[:,:,0] = state.informacoes['colors'][state.current_tissue -1][0] * state.masks + state.mask3d[:,:,0]*(~state.masks).astype('uint8')
                            state.mask3d[:,:,1] = state.informacoes['colors'][state.current_tissue -1][1] * state.masks + state.mask3d[:,:,1]*(~state.masks).astype('uint8')
                            state.mask3d[:,:,2] = state.informacoes['colors'][state.current_tissue -1][2] * state.masks + state.mask3d[:,:,2]*(~state.masks).astype('uint8')
                            self.plotsuperpixelmask.UpdateView()
                            
                    else:
                        size = state.informacoes["colors"].__len__()
                        state.informacoes["colors"].append(selectedColor)
                        state.informacoes["identifier"].append(size+1)
                        state.informacoes["tissue"].append(dictTissues[item])            
                        state.current_tissue = size+1  
                        self.current_tissue.setText(item)
            if state.informacoes["tissue"][state.current_tissue - 1] in [1, 2, 3]:
                state.selected_hu = state.fat_hu
            elif state.informacoes["tissue"][state.current_tissue - 1] in [5]:
                state.selected_hu = state.muscle_hu
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
        state.masks = np.zeros_like(state.segmented_mask, dtype="bool")
        
        state.mask3d = np.zeros((state.segmented_mask.shape[0],state.segmented_mask.shape[1],3), dtype = "uint8")
        if(state.file_name_global.split(".")[1] == "dcm"):
            state.mask3d[:,:,0] = state.dicom_image_array 
            state.mask3d[:,:,1] = state.dicom_image_array 
            state.mask3d[:,:,2] = state.dicom_image_array
        for i in range(state.informacoes["tissue"].__len__()):
            state.masks = np.zeros_like(state.segmented_mask, dtype="bool")
            state.masks[state.segmented_mask == state.informacoes["identifier"][i]] = 1
            state.mask3d[:,:,0] = state.informacoes['colors'][i][0] * state.masks + state.mask3d[:,:,0]*(~state.masks).astype('uint8')
            state.mask3d[:,:,1] = state.informacoes['colors'][i][1] * state.masks + state.mask3d[:,:,1]*(~state.masks).astype('uint8')
            state.mask3d[:,:,2] = state.informacoes['colors'][i][2] * state.masks + state.mask3d[:,:,2]*(~state.masks).astype('uint8')
        self.plotsuperpixelmask.showSavedMask()
        
        
    def open(self):
        """Open the interface to choose the file to display in the app"""
        state.previous_segments = {"superpixel":[], "previous_identifier":[]}
        state.previous_paints = []
        state.file_name = self.pathFile()
        if(state.file_name):
            state.superpixel_auth = False
            state.file_name_global = state.file_name
            if(state.file_name_global.split(".")[1] == "csv"):
                state.csv_flag = True
                state.segmented_mask, state.informacoes, state.area = load_mask(state.file_name_global)
                self.plotwidget_modify.axes.clear()
                self.plotwidget_modify.axes.set_title("Imagem Conferência")
                self.plotwidget_modify.axes.set_axis_off()   # remove os eixos 0.0–1.0
                self.plotwidget_modify.view.draw()
                state.dicom_image_array = []
                state.masks_empty = False
                state.current_tissue = 1
                self.set_color(QColor(
                    state.informacoes["colors"][0][0],
                    state.informacoes["colors"][0][1],
                    state.informacoes["colors"][0][2]
                ))
                self.recoveryMask3d()
                self.plotwidget_modify.axes.clear()
                self.plotwidget_modify.axes.set_title("Imagem Conferência")
                self.plotwidget_modify.view.draw()
                state.dicom_image_array = []
            else:
                dcm = pydicom.dcmread(state.file_name_global, force=True)
                state.dicom_image_array = dicom2array(dcm)
                if state.dicom_image_array is None:
                    QMessageBox.critical(self, "Erro", "Não foi possível ler o arquivo DICOM.")
                    return
                
                # Obter os valores na leitura de imagem no diretório
                state.muscle_hu = tissue_segmentation(select_RoI(state.dicom_image_array), "muscle")
                state.fat_hu = tissue_segmentation(select_RoI(state.dicom_image_array), "fat")
                state.selected_hu = np.ones((state.dicom_image_array.shape))
                
                state.dicom_image_array =  ConvertToUint8(state.dicom_image_array)
                state.area = np.count_nonzero(ConvertToUint8(select_RoI(state.dicom_image_array)))
                # self.plotwidget_original.on_change()
                self.plotwidget_modify.on_change()
                ok = 0
                if(state.csv_flag):
                    confirmDialog = CustomDialog()
                    ok = confirmDialog.show()
                if(ok):  
                    state.current_tissue = 1
                    self.set_color(QColor(state.informacoes["colors"][0][0], state.informacoes["colors"][0][1], state.informacoes["colors"][0][2]))
                    state.segments_global = []
                    self.recoveryMask3d()
                    state.masks_empty = False
                else:
                    state.mask3d = []
                    self.plotsuperpixelmask.im = ""
                    state.masks_empty = True
                    state.current_tissue = 0
                    state.segmented_mask = []
                    state.segments_global = []
                    state.informacoes = {"colors":[], "identifier":[], "tissue":[]}
                    item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                    while not ok:
                        item, ok = QInputDialog.getItem(self, "Select the region to paint", "List of regions", ("Fat","Intramuscular Fat", "Visceral Fat", "Bone", "Muscle", "Organ", "Other"), 0, False)
                    state.informacoes["colors"].append(np.array([255, 255, 0]))
                    state.informacoes["identifier"].append(1)
                    state.informacoes["tissue"].append(dictTissues[item]) 
                    state.current_tissue = 1
                    self.current_tissue.setText(item)
                    self.set_color(Qt.yellow)
                    if state.informacoes["tissue"][state.current_tissue - 1] in [1, 2, 3]:
                        state.selected_hu = state.fat_hu
                    elif state.informacoes["tissue"][state.current_tissue - 1] in [5]:
                        state.selected_hu = state.muscle_hu
                    imageViewer.plotsuperpixelmask.UpdateView()
                state.csv_flag = False
    def pathFile(self):
        """Get the path of the selected file"""
        state.file_name, _ = QFileDialog.getOpenFileName(self, "Open File",
                                                         state.open_dir, filter="DICOM (*.dcm *.);;csv(*.csv)")
        return state.file_name


    #Follow methods are self explanatory
    def HistMethodCLAHE(self):
        self.resetToggleState()

        if not np.array_equal(state.dicom_image_array, []):
            if(state.masks_empty == True):
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.HistMethodClahe()
            if(np.array_equal(state.segments_global, []) and not np.array_equal(state.mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            elif(not np.array_equal(state.mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            else:
                self.plotsuperpixelmask.UpdateView()  
    
    def SuperPixel(self):
        # self.plotwidget_original.SuperPixel()
        self.resetToggleState()
        if not np.array_equal(state.dicom_image_array, []):
            self.plotsuperpixelmask.SuperPixel()
            state.toggle_available = True

    def toggleRadioDensityCheck(self):
        if not np.array_equal(state.dicom_image_array, []):
            # self.plotsuperpixelmask.SuperPixel()
            state.radio_density_check_enabled = not state.radio_density_check_enabled

    def OriginalImage(self):
        # self.plotwidget_original.ResetDicom()
        self.resetToggleState()

        if state.file_name_global != '':
            if not state.file_name_global.split(".")[1] == "csv":
                self.plotwidget_modify.ResetDicom()
                if(state.masks_empty):
                    self.plotsuperpixelmask.im = ""
                if(np.array_equal(state.segments_global, []) and not np.array_equal(state.mask3d, [])):
                    self.plotsuperpixelmask.showSavedMask()
                elif(not np.array_equal(state.mask3d, [])):
                    self.recoveryMask3d()
                    self.plotsuperpixelmask.showSavedMask()
                else:
                    self.plotsuperpixelmask.UpdateView()  
    def RemoveObjects(self):
        # self.plotwidget_original.DeleteObjects()
        self.resetToggleState()

        if not np.array_equal(state.dicom_image_array, []):
            if(state.masks_empty == True):
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.DeleteObjects()
            if(np.array_equal(state.segments_global, []) and not np.array_equal(state.mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            elif(not np.array_equal(state.mask3d, [])):
                self.recoveryMask3d()
                self.plotsuperpixelmask.showSavedMask()
            else:
                self.plotsuperpixelmask.UpdateView()  
    def RemoveSkin(self):
            # self.plotwidget_original.DeleteObjects()
            self.resetToggleState()

            if not np.array_equal(state.dicom_image_array, []):
                if(state.masks_empty == True):
                    self.plotsuperpixelmask.im = ""
                self.plotwidget_modify.DeleteSkin()
                if(np.array_equal(state.segments_global, []) and not np.array_equal(state.mask3d, [])):
                    self.recoveryMask3d()
                    self.plotsuperpixelmask.showSavedMask()
                elif(not np.array_equal(state.mask3d, [])):
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
        if(not np.array_equal(state.dicom_image_array, [])):
            state.previous_paints = []
            state.mask3d = np.zeros((state.dicom_image_array.shape[0],state.dicom_image_array.shape[1],3), dtype = "uint8")
            state.mask3d[:,:,0] = state.dicom_image_array 
            state.mask3d[:,:,1] = state.dicom_image_array 
            state.mask3d[:,:,2] = state.dicom_image_array
            state.masks_empty = False
            state.previous_paints.append(copy.deepcopy(state.mask3d))
            imageViewer.plotsuperpixelmask.UpdateView()
    def calculatePercentages(self):
        state.graph = PercentagesGraph()
        state.graph.calculatePercentages()
        state.graph.show()
    def setDefaultOpen(self):
        Dir = QFileDialog.getExistingDirectory(self)
        if(Dir != ""):
            state.open_dir = Dir
            f = open("./defaultImageDir.txt", "w")
            f.write(state.open_dir)
            f.close()
    def setDefaultSave(self):
        Dir = QFileDialog.getExistingDirectory(self)
        
        if(Dir !=  ""):
            state.save_dir = Dir
            f = open("./defaultMaskDir.txt", "w")
            f.write(state.save_dir)
            f.close()
    def getDirsPath(self):
        if(path.exists("./defaultImageDir.txt")):
            f = open("./defaultImageDir.txt")
            state.open_dir = f.readline()
            f.close()
        if(path.exists("./defaultMaskDir.txt")):
            f = open("./defaultMaskDir.txt")
            state.save_dir = f.readline()
            f.close()
    def alternar(self):
        if(state.num_segments == 2000):
            state.num_segments = 500
        elif(state.num_segments == 500):
            state.num_segments = 5000
        else:
            state.num_segments = 2000

    def toggleSuperPixelView(self):
        if not state.toggle_available:
            QMessageBox.warning(self, "Aviso", "Você precisa aplicar o SuperPixel antes de usar o Toggle.")
            return
        
        state.superpixel_auth = not state.superpixel_auth
        state.show_superpixel = not state.show_superpixel
        print(f"SuperPíxel {'visível' if state.show_superpixel else 'oculto'}")
        self.plotsuperpixelmask.UpdateView()

    def resetToggleState(self):
        state.show_superpixel = True
        state.superpixel_auth = False
        state.toggle_available = False

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