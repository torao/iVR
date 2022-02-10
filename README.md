# iVR: Multi-Purpose Video Recorder for Raspberry Pi

The goal of iVR is to record long-term footage, either offline or online, with information acquired from various sensor devices. This repository contains scripts and setups to turn your Raspberry Pi
into a homebrew footage recorder. iVR might be used for the following purposes:

* **Security Camera**: for home, garage and warehouse
* **Dashboard Camera**: install at the front or rear of the vehicle
* **Observation**: landscape, plants, and animals

https://user-images.githubusercontent.com/836654/152195811-4a69e739-bfb7-4dc1-8158-f9dd9cd90fbc.mp4

Note, however, that iVR is intended to be a DIY footage recording device and does NOT guarantee
reliable footage recording.

The current iVR version only stores video files and does NOT have the ability to distribute live
streaming. Also, audio recording is still unstable and is turned off by default.

## Requirements

* Raspberry Pi or Raspberry Pi Zero:
  * 512MB+ memory
  * H.264 hardware encoder
  * Recommends quad-core CPU model
  * Latest [Raspberry Pi OS](https://www.raspberrypi.com/software/) (raspbian)
    * It may be available for other Linux operating systems with a few modifications
* USB storage:
  * FAT32 or exFAT format
  * Recommends 64GB+ (requires about 280MB to 360MB per hour)
  * Flash memory, SSD, HDD, etc.
* Camera:
  * Many USB Web cameras will work, but you may need to modify the script in some cases
  * MIPI camera module is also possible by directly specifying the device file
* GPS receiver
  * [Compatible with `gpsd`](https://gpsd.gitlab.io/gpsd/hardware.html)
  * Possible to use without GPS receiver, then the time and location information will not be
    displayed.
* Speaker
  * Optional, but recommended to notify errors and drives
  * USB, 3.5mm jack, HDMI, or bluetooth

Devices confirmed to work well:

* **Raspberry Pi**: 1 Model B+, 3 Model B, 3 Model B+
* **Storage**: XILOXIA 
* **Camera**: Logitech C207n

## Features

### Data Recording

The USB storage attached to the Raspberry Pi will be stored the following information:

* `footage-nnnnnn-YYYYMMDDHH.avi` - Video with time and location information on it.
* `tracklog-YYYYMMDD.gpx` - GPS positioning records.
* `ivr-YYYYMMDD.log` - Application log.

These files will be switched every hour or day. If the total size of the files exceeds the allowable
size, they will be deleted in order starting with the oldest file.

#### Footage File

The footage file is a AVI format that allows you to play back the video up to the point just before
the interruption, even if there is a sudden power failure.
This format can be played by Windows Standard Player and mac OS / Linux LVC. It can also be
converted to MP4 by `ffmpeg` as follows:

```
$ ffmpeg -i footage-xxx.avi footage-xxx.mp4
```

#### GPS Location File

GPS positioning records are saved in GPX format, which can be used by some location-based services
such as Google Earth.

The end of the file is often broken by sudden power-off, but it's a plain text (XML) file and can
be fixed manually :)

### Headless and Offline Environment

iVR assumes to be used headless, without a display or keyboard connected, in an environment that is
not connected to the Internet.
When an error or other event occurs, the speaker will be used to notify you. So it's recommended
that you connect a small speaker.
If you put a file named `announce.wav` in the `bin/` directory, that it will be played before every
notification.

Raspberry Pi doesn't have an RTC, so if it's not connected to a network (and cannot be synchronized
with NTP server), the local time will deviate significantly when the power is turned on and off.
The iVR has the ability to adjust the local time using the GPS time.

## Setup Your Raspberry Pi

Attach the USB storage, USB camera, and GPS receiver. And start up the Raspberry Pi.

If you have just installed the Raspberry Pi OS, it is recommended that you update your firmware and
system.

```
$ sudo apt-get update -y && sudo apt-get upgrade -y
$ sudo rpi-update
```

The iVR uses Ansible for its setup. You can setup locally on the Raspberry Pi's own localhost, or
remotely from Windows/macOS/Linux etc.

If you want to configure iVR on your Raspberry Pi local, you will need to install `git` and
`ansible` first. After then, The `PATH` will be added in the `.profile` so that you may need to do
`. .profile`, or logout/login.

```
$ sudo apt install -y git python3-pip
$ pip3 install ansible
$ . ~/.profile
```

Both of local and remote, clone the iVR repository and edit `startup.sh` to set the appropriate data
size limit for the USB storage to be used. For example, if you are using 128GB of USB storage, the
values would be as follows:

```
$ git clone https://github.com/torao/iVR.git
$ cd iVR
$ vi files/bin/startup.sh
...
COORDINATE_OPTIONS+=" --limit-footage 120G"
COORDINATE_OPTIONS+=" --limit-tracklog 5G"
```

To configure iVR from the localhost of Raspberry Pi itself, run Ansible as follows:

```
$ ansible-playbook -i hosts --connection=local site.yml
```

To configure iVR from the remote machine, configure the Raspberry Pi so that you can login using ssh,
and replace `localhost` in the [`hosts`](/torao/iVR/tree/main/hosts) file with the hostname or IP
address of the machine you want to setup.

```
$ vi hosts
[all]
192.168.xxx.yyy
...
$ ansible-playbook -i hosts site.yml
```

> It also possible to setup iVR by manually doing the steps described in 
> [`site.yml`](/torao/iVR/tree/main/site.yml). In this case, you could use regular Linux instead of
> Raspberry Pi. If you are doing this operation for the sake of learning Linux, doing everything
> manually may help you understand the system.

After Ansible has been successfully finished, making sure the camera and GPS receiver are connected
and reboot your Raspberry Pi.

When iVR starts correctly, you should see the following three python processes running.

```
$ ps -ef | grep python
pi  778  1 83 01:08 ?  00:13:25 python3 /opt/ivr/bin/gpslog.py
pi  779  1  0 01:08 ?  00:00:00 python3 /opt/ivr/bin/coordinate.py
pi  780  1  0 01:08 ?  00:00:00 python3 /opt/ivr/bin/record.py
```

In addition, recording should have started and footage files and logs should have been generated in
the `/opt/ivr/data/` directory. If one of the python processes fails to start, please refer to
`/opt/ivr/data/ivr-YYYYMMDD.log` or `~/ivr-boot.log`.

## System Structure

![system-boundary](https://user-images.githubusercontent.com/836654/152196050-de549dc6-e55d-4c96-9122-d0dfad279cec.png)

## License

[MIT License](/torao/iVR/tree/main/LICENSE)
