#! /usr/bin/env python3
"""
diskimgr, automated reading of optical media
Graphical user interface

Author: Johan van der Knijff
Research department,  KB / National Library of the Netherlands
"""

import sys
import os
import io
import time
import threading
import logging
import queue
import uuid
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog as tkFileDialog
from tkinter import scrolledtext as ScrolledText
from tkinter import messagebox as tkMessageBox
from tkinter import ttk
from tkfilebrowser import askopendirname
from .disk import Disk
from . import shared
from . import config


class omimgrGUI(tk.Frame):

    """This class defines the graphical user interface + associated functions
    for associated actions
    """

    def __init__(self, parent, *args, **kwargs):
        """Initiate class"""
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.root = parent
        # Logging stuff
        self.logger = logging.getLogger()
        # Create a logging handler using a queue
        self.log_queue = queue.Queue(-1)
        self.queue_handler = QueueHandler(self.log_queue)
        # Create disc instance
        self.disk = Disk()
        self.t1 = None
        # Read configuration file
        self.disk.getConfiguration()
        # Set dirOut, depending on whether value from config is a directory
        if os.path.isdir(self.disk.defaultDir):
            self.disk.dirOut = self.disk.defaultDir
        else:
            self.disk.dirOut = os.path.expanduser("~")

        # Build the GUI
        self.build_gui()

    def on_quit(self, event=None):
        """Quit diskimgr"""
        os._exit(0)

    def on_submit(self, event=None):
        """fetch and validate entered input, and start processing"""

        # This flag is true if all input validates
        inputValidateFlag = True

        # Fetch entered values (strip any leading / trailing whitespace characters)
        #self.disk.blockDevice = self.omDevice_entry.get().strip()
        self.disk.blockDevice =  self.bdVar.get().split(' (')[0].strip()
        self.disk.blockSize = self.blockSize_entry.get().strip()

        # Lookup readMethod for readMethodCode value
        readMethodCode = self.v.get()
        for i in self.readMethods:
            if i[1] == readMethodCode:
                self.disk.readMethod = i[0]

        self.disk.retries = self.retries_entry.get().strip()
        self.disk.prefix = self.prefix_entry.get().strip()
        self.disk.extension = self.extension_entry.get().strip()
        self.disk.identifier = self.identifier_entry.get().strip()
        self.disk.description = self.description_entry.get().strip()
        self.disk.notes = self.notes_entry.get(1.0, tk.END).strip()
        self.disk.rescueDirectDiscMode = self.rescueDirectDiscMode.get()
        self.disk.autoRetry = self.autoRetry.get()

        # Validate input
        self.disk.validateInput()

        # Show error message for any parameters that didn't pass validation
        if not self.disk.dirOutIsDirectory:
            inputValidateFlag = False
            msg = ("Output directory doesn't exist:\n" + self.disk.dirOut)
            tkMessageBox.showerror("ERROR", msg)

        if not self.disk.dirOutIsWritable:
            inputValidateFlag = False
            msg = ('Cannot write to directory ' + self.disk.dirOut)
            tkMessageBox.showerror("ERROR", msg)

        if not self.disk.deviceExistsFlag:
            inputValidateFlag = False
            msg = ('Selected device does not exist')
            tkMessageBox.showerror("ERROR", msg)

        if not self.disk.deviceAccessibleFlag:
            inputValidateFlag = False
            msg = ('Selected device is not accessible')
            tkMessageBox.showerror("ERROR", msg)

        if self.disk.insufficientSpaceFlag:
            inputValidateFlag = False
            msg = ('Size of ' + self.disk.blockDevice + 
                   ' exceeds available space in ' + self.disk.dirOut)
            tkMessageBox.showerror("ERROR", msg)

        if not self.disk.ddInstalled:
            inputValidateFlag = False
            msg = ("dd not installed!")
            tkMessageBox.showerror("ERROR", msg)

        if not self.disk.ddrescueInstalled:
            inputValidateFlag = False
            msg = ("ddrescue not installed!\n"
                   "install with:\n"
                   "'sudo apt install gddrescue'")
            tkMessageBox.showerror("ERROR", msg)

        # Ask confirmation if dd is used on dir with existing files
        outDirConfirmFlag = True
        if self.disk.outputExistsFlag and self.disk.readMethod == 'dd':
            msg = ('writing to ' + self.disk.dirOut + ' will overwrite existing files!\n'
                   'press OK to continue, otherwise press Cancel')
            outDirConfirmFlag = tkMessageBox.askokcancel("Overwrite files?", msg)
            if outDirConfirmFlag:
                # Delete old image file (and map file, if it exists)
                os.remove(self.disk.imageFile)
                try:
                    os.remove(self.disk.mapFile)
                except OSError:
                    pass
            else:
                inputValidateFlag = False
        # If ddrescue is used, delete old image file, but only if no map file
        # can be found (which indicates readom output)
        elif self.disk.outputExistsFlag and self.disk.readMethod == 'ddrescue':
            if not os.path.isfile(self.disk.mapFile):
                try:
                    os.remove(self.disk.imageFile)
                except:
                    pass

        if inputValidateFlag:

            # Start logger
            successLogger = True
            try:
                self.setupLogger()
                # Start polling log messages from the queue
                self.after(100, self.poll_log_queue)
            except OSError:
                # Something went wrong while trying to write to log file
                msg = ('error trying to write log file to ' + self.disk.logFile)
                tkMessageBox.showerror("ERROR", msg)
                successLogger = False

            if successLogger:
                # Enable interrupt button
                self.interrupt_button.config(state='normal')
                # Disable data entry widgets
                self.outDirButton_entry.config(state='disabled')
                self.omDevice_entry.config(state='disabled')
                self.refresh_button.config(state='disabled')
                self.retries_entry.config(state='disabled')
                self.decreaseRetriesButton.config(state='disabled')
                self.increaseRetriesButton.config(state='disabled')
                self.blockSize_entry.config(state='disabled')
                self.decreaseBSButton.config(state='disabled')
                self.increaseBSButton.config(state='disabled')
                self.rescueDirectDiscMode_entry.config(state='disabled')
                self.autoRetry_entry.config(state='disabled')
                self.prefix_entry.config(state='disabled')
                self.extension_entry.config(state='disabled')
                self.rbDd.config(state='disabled')
                self.rbRescue.config(state='disabled')
                self.identifier_entry.config(state='disabled')
                self.loadJsonButton.config(state='disabled')
                self.uuidButton.config(state='disabled')
                self.description_entry.config(state='disabled')
                self.notes_entry.config(state='disabled')
                self.start_button.config(state='disabled')
                self.quit_button.config(state='disabled')

                # Launch disc processing function as subprocess
                self.t1 = threading.Thread(target=self.disk.processDisk)
                self.t1.start()


    def selectOutputDirectoryOld(self, event=None):
        """Select output directory"""
        dirInit = self.disk.dirOut
        self.disk.dirOut = tkFileDialog.askdirectory(initialdir=dirInit)
        self.outDirLabel['text'] = self.disk.dirOut


    def selectOutputDirectory(self, event=None):
        """Select output directory"""
        dirInit = self.disk.dirOut
        self.disk.dirOut = askopendirname(initialdir=dirInit)
        self.outDirLabel['text'] = self.disk.dirOut


    def importMetadata(self, event=None):

        metadataFileExists = True
        loadSuccessFlag = True
        """Set prefix, extension, identifier, description, notes
        according to existing metadata file"""
        metadataFile = os.path.join(self.disk.dirOut, self.disk.metadataFileName)

        if not os.path.isfile(metadataFile):
            metadataFileExists = False
            msg = ('No metadata file found in directory ' + self.disk.dirOut + '!')
            tkMessageBox.showerror("ERROR", msg)

        if metadataFileExists:

            try:
                with io.open(metadataFile, 'r', encoding='utf-8') as f:
                    mdDict = json.load(f)

            except IOError:
                loadSuccessFlag = False
                msg = ("An error occurred while trying to read  " + metadataFile)
                tkMessageBox.showerror("ERROR", msg)
            except ValueError:
                loadSuccessFlag = False
                msg = ("Cannote decode JSON from "  + metadataFile)
                tkMessageBox.showerror("ERROR", msg)
        
            if loadSuccessFlag:
                try:         
                    self.prefix_entry.delete(0, tk.END)
                    self.prefix_entry.insert(tk.END, mdDict['prefix'])
                    self.extension_entry.delete(0, tk.END)
                    self.extension_entry.insert(tk.END, mdDict['extension'])
                    self.identifier_entry.delete(0, tk.END)
                    self.identifier_entry.insert(tk.END, mdDict['identifier'])
                    self.description_entry.delete(0, tk.END)
                    self.description_entry.insert(tk.END, mdDict['description'])
                    self.notes_entry.delete(1.0, tk.END)
                    self.notes_entry.insert(tk.END, mdDict['notes'])
                except KeyError:
                    msg = ("Parsing of metadata file resulted in an error")
                    tkMessageBox.showerror("ERROR", msg)


    def refreshDevices(self, event=None):
        """Refresh list of available devices"""
        devices = shared.getBlockDevices()
        DEVICES = []
        for device in devices:
            # Display both device with its corresponding size
            DEVICES.append(device[0] + ' (' + device[1] + ')')
        
        self.omDevice_entry.set_menu(*DEVICES)

    def interruptImaging(self, event=None):
        """Interrupt imaging process"""
        config.interruptFlag = True
        self.interrupt_button.configure(state='disabled')

    def decreaseRetries(self, event=None):
        """Decrease value of retries"""
        try:
            retriesOld = int(self.retries_entry.get().strip())
        except ValueError:
            # Reset if user manually entered something weird
            retriesOld = int(self.disk.retriesDefault)
        retriesNew = max(0, retriesOld - 1)
        self.retries_entry.delete(0, tk.END)
        self.retries_entry.insert(tk.END, str(retriesNew))

    def increaseRetries(self, event=None):
        """Increase value of retries"""
        try:
            retriesOld = int(self.retries_entry.get().strip())
        except ValueError:
            # Reset if user manually entered something weird
            retriesOld = int(self.disk.retriesDefault)
        retriesNew = retriesOld + 1
        self.retries_entry.delete(0, tk.END)
        self.retries_entry.insert(tk.END, str(retriesNew))

    def decreaseBlocksize(self):
        """Decrease value of blockSize"""
        try:
            blockSizeOld = int(self.blockSize_entry.get().strip())
        except ValueError:
            # Reset if user manually entered something weird
            blockSizeOld = int(self.disk.blockSizeDefault)
        blockSizeNew = max(blockSizeOld - 512, 512)
        self.blockSize_entry.delete(0, tk.END)
        self.blockSize_entry.insert(tk.END, str(blockSizeNew))

    def increaseBlocksize(self):
        """Increase value of blockSize"""
        try:
            blockSizeOld = int(self.blockSize_entry.get().strip())
        except ValueError:
            # Reset if user manually entered something weird
            blockSizeOld = int(self.disk.blockSizeDefault)
        blockSizeNew = blockSizeOld + 512
        self.blockSize_entry.delete(0, tk.END)
        self.blockSize_entry.insert(tk.END, str(blockSizeNew))

    def insertUUID(self, event=None):
        """Insert UUID into identifier field"""
        myID = str(uuid.uuid1())
        self.identifier_entry.delete(0, tk.END)
        self.identifier_entry.insert(tk.END, myID)

    def build_gui(self):
        """Build the GUI"""

        self.root.title('diskimgr v.' + config.version)
        self.root.option_add('*tearOff', 'FALSE')
        self.grid(column=0, row=0, sticky='w')
        self.grid_columnconfigure(0, weight=1, pad=0)
        self.grid_columnconfigure(1, weight=1, pad=0)
        self.grid_columnconfigure(2, weight=1, pad=0)
        self.grid_columnconfigure(3, weight=1, pad=0)

        # Entry elements
        ttk.Separator(self, orient='horizontal').grid(column=0, row=0, columnspan=4, sticky='ew')
        # Output Directory
        self.outDirButton_entry = tk.Button(self,
                                            text='Select Output Directory',
                                            underline=14,
                                            command=self.selectOutputDirectory,
                                            width=20)
        self.outDirButton_entry.grid(column=0, row=3, sticky='w')
        self.outDirLabel = tk.Label(self, text=self.disk.dirOut)
        self.outDirLabel.update()
        self.outDirLabel.grid(column=1, row=3, sticky='w')

        ttk.Separator(self, orient='horizontal').grid(column=0, row=4, columnspan=4, sticky='ew')

        # Device
        devices = shared.getBlockDevices()
        DEVICES = []
        for device in devices:
            # Display both device with its corresponding size
            DEVICES.append(device[0] + ' (' + device[1] + ')')
        self.bdVar = tk.StringVar()
        try:
            self.bdVar.set(DEVICES[0])
        except IndexError:
            # We end up here if diskimgr is launched with insufficient rights
            # or user is not part of disk group
            self.bdVar.set("N/A")
        self.omDevice_entry = ttk.OptionMenu(self, self.bdVar, *DEVICES)
        
        tk.Label(self, text='Block device').grid(column=0, row=5, sticky='w')
        self.omDevice_entry.grid(column=1, row=5, sticky='w')

        # Refresh device list button
        self.refresh_button = tk.Button(self,
                                        text='Refresh',
                                        underline=0,
                                        command=self.refreshDevices,
                                        width=4)
        self.refresh_button.grid(column=1, row=5, sticky='e')

        # Block Size
        tk.Label(self, text='Block Size').grid(column=0, row=6, sticky='w')
        self.blockSize_entry = tk.Entry(self, width=20)
        self.blockSize_entry['background'] = 'white'
        self.blockSize_entry.insert(tk.END, self.disk.blockSize)
        self.blockSize_entry.grid(column=1, row=6, sticky='w')
        self.decreaseBSButton = tk.Button(self, text='-', command=self.decreaseBlocksize, width=1)
        self.decreaseBSButton.grid(column=1, row=6, sticky='e')
        self.increaseBSButton = tk.Button(self, text='+', command=self.increaseBlocksize, width=1)
        self.increaseBSButton.grid(column=2, row=6, sticky='w')

        # Read command (dd or ddrescue)
        self.v = tk.IntVar()
        self.v.set(1)

        # List with all possible read methods, corresponding button codes, keyboard
        # shortcut character (keyboard shortcuts not actually used yet)
        self.readMethods = [
            ['dd', 1, 0],
            ['ddrescue', 2, 3],
        ]

        tk.Label(self, text='Read method').grid(column=0, row=7, sticky='w')

        self.rbDd = tk.Radiobutton(self,
                                    text='dd',
                                    variable=self.v,
                                    value=1)
        self.rbDd.grid(column=1, row=7, sticky='w')

        self.rbRescue = tk.Radiobutton(self,
                                    text='ddrescue',
                                    variable=self.v,
                                    value=2)
        self.rbRescue.grid(column=1, row=8, sticky='w')

        # Retries
        tk.Label(self, text='Retries (ddrescue)').grid(column=0, row=9, sticky='w')
        self.retries_entry = tk.Entry(self, width=20)
        self.retries_entry['background'] = 'white'
        self.retries_entry.insert(tk.END, self.disk.retriesDefault)
        self.retries_entry.grid(column=1, row=9, sticky='w')
        self.decreaseRetriesButton = tk.Button(self, text='-',
                                               command=self.decreaseRetries,
                                               width=1)
        self.decreaseRetriesButton.grid(column=1, row=9, sticky='e')
        self.increaseRetriesButton = tk.Button(self, text='+',
                                               command=self.increaseRetries,
                                               width=1)
        self.increaseRetriesButton.grid(column=2, row=9, sticky='w')

        # Direct disc mode
        tk.Label(self, text='Direct disc mode (ddrescue)').grid(column=0, row=10, sticky='w')
        self.rescueDirectDiscMode = tk.BooleanVar()
        self.rescueDirectDiscMode.set(self.disk.rescueDirectDiscMode)
        self.rescueDirectDiscMode_entry = tk.Checkbutton(self, variable=self.rescueDirectDiscMode)
        self.rescueDirectDiscMode_entry.grid(column=1, row=10, sticky='w')
    
        # Direct disc mode
        tk.Label(self, text='Auto-retry with ddrescue on dd failure').grid(column=0, row=11, sticky='w')
        self.autoRetry = tk.BooleanVar()
        self.autoRetry.set(self.disk.autoRetry)
        self.autoRetry_entry = tk.Checkbutton(self, variable=self.autoRetry)
        self.autoRetry_entry.grid(column=1, row=11, sticky='w')

        ttk.Separator(self, orient='horizontal').grid(column=0, row=12, columnspan=4, sticky='ew')

        # Load from json
        self.loadJsonButton = tk.Button(self,
                                            text='Load existing metadata',
                                            underline=0,
                                            command=self.importMetadata,
                                            width=20)
        self.loadJsonButton.grid(column=0, row=13, sticky='w')
    
        # Prefix
        tk.Label(self, text='Prefix').grid(column=0, row=14, sticky='w')
        self.prefix_entry = tk.Entry(self, width=20)
        self.prefix_entry['background'] = 'white'
        self.prefix_entry.insert(tk.END, self.disk.prefix)
        self.prefix_entry.grid(column=1, row=14, sticky='w')

        # Extension
        tk.Label(self, text='Extension').grid(column=0, row=15, sticky='w')
        self.extension_entry = tk.Entry(self, width=20)
        self.extension_entry['background'] = 'white'
        self.extension_entry.insert(tk.END, self.disk.extension)
        self.extension_entry.grid(column=1, row=15, sticky='w')

        # Identifier entry field
        tk.Label(self, text='Identifier').grid(column=0, row=16, sticky='w')
        self.identifier_entry = tk.Entry(self, width=35)
        self.identifier_entry['background'] = 'white'
        self.identifier_entry.insert(tk.END, self.disk.identifier)
        self.identifier_entry.grid(column=1, row=16, sticky='w')
        self.uuidButton = tk.Button(self, text='UUID',
                                    underline=0, command=self.insertUUID,
                                    width=2)
        self.uuidButton.grid(column=1, row=16, sticky='e')

        # Description entry field
        tk.Label(self, text='Description').grid(column=0, row=17, sticky='w')
        self.description_entry = tk.Entry(self, width=45)
        self.description_entry['background'] = 'white'
        self.description_entry.insert(tk.END, self.disk.description)
        self.description_entry.grid(column=1, row=17, sticky='w', columnspan=1)

        # Notes entry field
        tk.Label(self, text='Notes').grid(column=0, row=18, sticky='w')
        self.notes_entry = tk.Text(self, height=6, width=45)
        self.notes_entry['background'] = 'white'
        self.notes_entry.insert(tk.END, self.disk.notes)
        self.notes_entry.grid(column=1, row=18, sticky='w', columnspan=1)

        ttk.Separator(self, orient='horizontal').grid(column=0, row=19, columnspan=4, sticky='ew')

        self.start_button = tk.Button(self,
                                      text='Start',
                                      width=10,
                                      underline=0,
                                      command=self.on_submit)
        self.start_button.grid(column=1, row=20, sticky='w')

        self.quit_button = tk.Button(self,
                                     text='Exit',
                                     width=10,
                                     underline=0,
                                     command=self.on_quit)
        self.quit_button.grid(column=1, row=20, sticky='e')

        # Interrupt button (disabled on startup)
        self.interrupt_button = tk.Button(self,
                                          text='Interrupt',
                                          underline=0,
                                          command=self.interruptImaging,
                                          width=8)
        self.interrupt_button.grid(column=1, row=21, sticky='w')
        self.interrupt_button.config(state='disabled')

        ttk.Separator(self, orient='horizontal').grid(column=0, row=22, columnspan=4, sticky='ew')

        # Add ScrolledText widget to display logging info
        self.st = ScrolledText.ScrolledText(self, state='disabled', height=15)
        self.st.configure(font='TkFixedFont')
        self.st['background'] = 'white'
        self.st.grid(column=0, row=23, sticky='ew', columnspan=4)

        # Define bindings for keyboard shortcuts: buttons
        self.root.bind_all('<Control-Key-d>', self.selectOutputDirectory)
        self.root.bind_all('<Control-Key-i>', self.interruptImaging)
        self.root.bind_all('<Control-Key-s>', self.on_submit)
        self.root.bind_all('<Control-Key-e>', self.on_quit)
        self.root.bind_all('<Control-Key-u>', self.insertUUID)
        self.root.bind_all('<Control-Key-l>', self.importMetadata)
        self.root.bind_all('<Control-Key-r>', self.refreshDevices)
          
        for child in self.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # Display message and exit if config file could not be read
        if not self.disk.configSuccess:
            msg = ("Error reading configuration file! \n" +
                   "Run '(sudo) diskimgr-config' to fix this.")
            errorExit(msg)

    def reset_gui(self, dirOut):
        """Reset the GUI"""
        # Create new disc instance
        self.disk = Disk()
        # Read configuration
        self.disk.getConfiguration()
        # Set dirOut
        self.disk.dirOut = dirOut
        # Set readMethod to readom
        self.v.set(1)
        # Logging stuff
        self.logger = logging.getLogger()
        # Create a logging handler using a queue
        self.log_queue = queue.Queue(-1)
        self.queue_handler = QueueHandler(self.log_queue)
        # Disable interrupt button
        self.interrupt_button.config(state='disabled')
        # Enable entry widgets
        self.outDirButton_entry.config(state='normal')
        self.omDevice_entry.config(state='normal')
        self.refresh_button.config(state='normal')
        self.retries_entry.config(state='normal')
        self.decreaseRetriesButton.config(state='normal')
        self.increaseRetriesButton.config(state='normal')
        self.blockSize_entry.config(state='normal')
        self.decreaseBSButton.config(state='normal')
        self.increaseBSButton.config(state='normal')
        self.rescueDirectDiscMode_entry.config(state='normal')
        self.autoRetry_entry.config(state='normal')
        self.prefix_entry.config(state='normal')
        self.extension_entry.config(state='normal')
        self.rbDd.config(state='normal')
        self.rbRescue.config(state='normal')
        self.loadJsonButton.config(state='normal')
        self.identifier_entry.config(state='normal')
        self.uuidButton.config(state='normal')
        self.description_entry.config(state='normal')
        self.notes_entry.config(state='normal')
        self.start_button.config(state='normal')
        self.quit_button.config(state='normal')
        # Reset all entry widgets
        self.outDirLabel['text'] = self.disk.dirOut
        self.refreshDevices()
        self.retries_entry.delete(0, tk.END)
        self.retries_entry.insert(tk.END, self.disk.retriesDefault)
        self.prefix_entry.delete(0, tk.END)
        self.prefix_entry.insert(tk.END, self.disk.prefix)
        self.extension_entry.delete(0, tk.END)
        self.extension_entry.insert(tk.END, self.disk.extension)
        self.identifier_entry.delete(0, tk.END)
        self.identifier_entry.insert(tk.END, self.disk.identifier)
        self.description_entry.delete(0, tk.END)
        self.description_entry.insert(tk.END, self.disk.description)
        self.notes_entry.delete(1.0, tk.END)
        self.notes_entry.insert(tk.END, self.disk.notes)
        self.rescueDirectDiscMode.set(self.disk.rescueDirectDiscMode)
        self.autoRetry.set(self.disk.autoRetry)
        self.start_button.config(state='normal')
        self.quit_button.config(state='normal')

    def setupLogger(self):
        """Set up logger configuration"""

        # Basic configuration
        logging.basicConfig(filename=self.disk.logFile,
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

        # Add the handler to logger
        self.logger = logging.getLogger()

        # This sets the console output format (slightly different from basicConfig!)
        formatter = logging.Formatter('%(message)s')
        self.queue_handler.setFormatter(formatter)
        self.logger.addHandler(self.queue_handler)

    def display(self, record):
        """Display log record in scrolledText widget"""
        msg = self.queue_handler.format(record)
        self.st.configure(state='normal')
        self.st.insert(tk.END, msg + '\n', record.levelname)
        self.st.configure(state='disabled')

        # Autoscroll to the bottom
        self.st.yview(tk.END)

    def poll_log_queue(self):
        """Check every 100ms if there is a new message in the queue to display"""
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display(record)
        self.after(100, self.poll_log_queue)


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue

    It can be used from different threads
    The ConsoleUi class polls this queue to display records in a ScrolledText widget
    Taken from https://github.com/beenje/tkinter-logging-text-widget/blob/master/main.py
    """

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


def checkDirExists(dirIn):
    """Check if directory exists and exit if not"""
    if not os.path.isdir(dirIn):
        msg = ('directory ' + dirIn + ' does not exist!')
        tkMessageBox.showerror("Error", msg)
        sys.exit(1)


def errorExit(error):
    """Show error message in messagebox and then exit after user presses OK"""
    tkMessageBox.showerror("Error", error)
    os._exit(1)


def main():
    """Main function"""

    packageDir = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    root.iconphoto(True, tk.PhotoImage(file=os.path.join(packageDir, 'icons', 'diskimgr.png')))
    myGUI = omimgrGUI(root)
    # This ensures application quits normally if user closes window
    root.protocol('WM_DELETE_WINDOW', myGUI.on_quit)
    retryFromDdFlag = False
    retryFromRescueFlag = False

    while True:
        try:
            root.update_idletasks()
            root.update()
            time.sleep(0.1)
            if myGUI.disk.finishedFlag:
                myGUI.t1.join()
                handlers = myGUI.logger.handlers[:]
                for handler in handlers:
                    handler.close()
                    myGUI.logger.removeHandler(handler)

                if myGUI.disk.successFlag and not myGUI.disk.readErrorFlag:
                    # Imaging completed with no errors
                    msg = ('Disk processed without errors')
                    tkMessageBox.showinfo("Success", msg)
                elif myGUI.disk.readMethod == 'dd' and myGUI.disk.autoRetry:
                    # Imaging resulted in errors, auto-retry with ddrescue
                    retryFromDdFlag = True
                elif myGUI.disk.readMethod == 'dd' and not myGUI.disk.autoRetry:
                    # Imaging resulted in errors, as if user wants to retry with ddrescue
                    msg = ('Errors occurred while processing this disk\n'
                           'Try again with ddrescue? (This will overwrite\n'
                           'existing image file)')
                    if tkMessageBox.askyesno("Errors", msg):
                        retryFromDdFlag = True
                elif myGUI.disk.readMethod == 'ddrescue':
                    # Imaging resulted in errors
                    msg = ('One or more errors occurred while processing disk\n'
                           'Try another ddrescue pass? (Hint: you may try using\n'
                           'Direct Disc mode and/or another reader device)')
                    if tkMessageBox.askyesno("Errors", msg):
                        retryFromRescueFlag = True

                if retryFromDdFlag:
                    # Reset flags
                    myGUI.disk.readErrorFlag = False
                    myGUI.disk.finishedFlag = False
                    # Set readMethod to ddrescue
                    myGUI.v.set(2)
                    myGUI.on_submit()
                    retryFromDdFlag = False
                elif retryFromRescueFlag:
                    # Reset flags
                    myGUI.disk.readErrorFlag = False
                    myGUI.disk.finishedFlag = False
                    # Enable entry widgets
                    myGUI.omDevice_entry.config(state='normal')
                    myGUI.retries_entry.config(state='normal')
                    myGUI.decreaseRetriesButton.config(state='normal')
                    myGUI.increaseRetriesButton.config(state='normal')
                    myGUI.rescueDirectDiscMode_entry.config(state='normal')
                    myGUI.autoRetry_entry.config(state='normal')
                    myGUI.start_button.config(state='normal')
                    myGUI.quit_button.config(state='normal')
                    myGUI.interrupt_button.config(state='disabled')
                    myGUI.refresh_button.config(state='normal')
                    retryFromRescueFlag = False
                else:
                    # Reset dirOut to parent dir of current value (returns root 
                    # dir if dirOut is root)
                    dirOutNew = str(Path(myGUI.disk.dirOut).parent)
                    # Reset the GUI
                    myGUI.reset_gui(dirOutNew)

        except Exception as e:
            # Unexpected error
            msg = 'An unexpected error occurred, see log file for details'
            logging.error(e, exc_info=True)
            errorExit(msg)

if __name__ == "__main__":
    main()
