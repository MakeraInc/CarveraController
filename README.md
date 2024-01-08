This repository manages binary releases of [CarveraController](https://www.makera.com). 

Checkout the [Releases Page](https://github.com/MakeraInc/CarveraController/releases) for downloads.

----

# Installation


## Windows Installation
![Windows Setup](/img/Windows-Setup.png)

1. Launch the installer executable
2. Windows may ask if you trust the software, as Carvera Controller is not currently digitally signed
3. Select if you would like to create a desktop icon
4. Click *Install*
5. Click *Finish*

That's it! Locate the Carvera Controller icon to launch the program

### Install Windows USB Driver (if you connect the machine via USB)

After connecting the USB into your computer. Then open the device manager and under the **Other devices** tab you should see it as **FTDI 232R UART**. If it shows up there correctly then follow the steps from **"STEP 1"**. And if it shows up as **USB Serial Port**. In that case simply follow the steps from **"STEP 2"**.

**Step 1: Installing First Set of USB drivers**

![USB Driver Setup1](/img/USB-Driver-Setup-1.png)

Firstly, Open the device manager, right click on the FTDI and click on **Update drivers**. Then click on **Browse My computer for drivers** and then just select the driver Folder where you downloaded the drivers. And then hit ok, make sure **Include Subfolder** is ticked. And now click on **Next** and it will install first set of drivers

**Step 2: Installing Second Set of USB drivers**

![USB Driver Setup2](/img/USB-Driver-Setup-2.png)

This time it will show up as **USB Serial Port** under **other devices**. So now again right click on it and **select update drivers**. Then again click on **Browse My computer for drivers**. And then just select the driver Folder and hit ok again, make sure **Include Subfolder** is ticked. And now click on **Next** and it will install the second set of drivers. Which is same process as first one. 

If everything is done correctly, then the drivers will be installed and now you can use your USB without any problem.

## Mac/OSX Installation
![Mac OS Setup](/img/Mac-Setup.png)

1. Double-click the dmg file to mount it 
2. Drag the CarveraController application into your applications folder
3. Launch CarveraController from the launcher as normal
4. You can now eject the DMG file (drag it to the trash bin)

### Solution for APP damage error
![APP Damage](/img/APP-Damage-Error.png)

If you encounter the warning as above, open the terminal window and execute the command below:

**sudo xattr -r -d com.apple.quarantine /Applications/CarveraController.app**

![APP Damage Solution](/img/APP-Damage-solution.png)

Reopen the CarveraController application, it should be OK now.

If you still experience a crash, please execute the following command:

**open /Applications/CarveraController.app/Contents/MacOS/carvera**

After this, you can directly open it next time.


## Android Installation

1. Open your Android device's file explorer app. ...
2. Locate your APK file in your file explorer app and select it.
3. The APK installer menu will appear—tap Install. ...
4. Allow time for the app to install.
5. Tap Done or Open once the installation is complete.



