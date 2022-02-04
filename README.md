# iVR: Multi-Purpose Video Recorder for Raspberry Pi

The goal of iVR is to record long-term footage with information acquired from various sensor
devices. This repository contains scripts and setups to turn your Raspberry Pi into a homebrew
video recorder. It might be used for the following purposes:

* **Security Camera**: for home, garage and warehouse
* **Dashboard Camera**: install at the front or rear of the vehicle
* **Observation**: landscape, plants, and animals

The current iVR version only stores video files and does NOT have the ability to distribute live
video.

https://user-images.githubusercontent.com/836654/152195811-4a69e739-bfb7-4dc1-8158-f9dd9cd90fbc.mp4

## Requirements

* Raspberry Pi or Raspberry Pi Zero:
  * 512MB+ Memory
  * H.264 hardware encoder
  * Recommends quad-core CPU model
* USB storage:
  * Recommends 64GB+ (footage 60GB+, tracklog 2GB+)
  * Requires 280～360MB per hour
  * It doesn't matter if it's flash memory or HDD
* Camera:
  * 30fps+
  * Recommends generic USB camera (MIPI camera module is also possible by directly specifying the device file)
* GPS receiver
  * needs to be recognizable by `gpsd`
  * It's possible to use without GPS receiver, then the time and location information will not be
    displayed.

## Features

The USB storage installed in the Raspberry Pi will be stored the following information:

* `footage-nnnnnn-YYYYMMDDHH.avi` - A video with time and location information on it.
* `tracklog-YYYYMMDD.gpx` - Location (a format that can be used by some location-based services).
* `ivr-YYYYMMDD.log` - Application log.

These files will be switched every hour or day. If the total size of the files exceeds the allowable
size, they will be deleted in order starting with the oldest file.

## Setup Your Raspberry Pi

If you have just installed the Raspberry Pi OS, it is recommended that you update your firmware and
system.

```
$ sudo apt-get update -y && sudo apt-get upgrade -y
$ sudo rpi-update
```

Install `git` and `ansible`. The `PATH` will be added in the `.profile` so that you may need to do
`. .profile`, or logout/login.

```
$ sudo apt install -y git python3-pip
$ pip3 install ansible
$ . ~/.profile
```

Clone this repository locally and run ansible.

```
$ git clone https://github.com/torao/iVR.git
$ cd iVR
$ ansible-playbook -i hosts --connection=local site.yml
```

iVR is set up using Ansible. Therefore, you will have to configure your Raspberry Pi manually until
it's able to login via ssh.

You can setup iVR without Ansible by manually following the steps described in
[`site.yml`](/torao/iVR/tree/main/site.yml). If you are doing this operation for the sake of
learning Linux, doing everything manually will help you understand the system.

### Work that must be done manually

In order to configure the Raspberry Pi with Ansible after installing the OS, you need to be able to
connect to it externally via ssh.

- Run `raspi-config`.
  - Allow ssh connection (required).
  - Your own system-specific settings such as WiFi, password, hostname, locale, and time zone
    (optional).
- Firmware update with `rpi-update`.

### Modify Ansible configuration and iVR scripts

Edit the [`hosts`](/torao/iVR/tree/main/hosts) file to set the connection information for the target
Raspberry Pi. For example, if you are setting up a Raspberry Pi for 192.168.0.12, modify the
contents of the `hosts` file as follows, and if you have changed the ssh port or password, modify
them as well.

```
$ cat hosts
[all]
192.168.0.12

[all:vars]
ansible_ssh_port=22
ansible_ssh_user=pi
ansible_ssh_pass=raspberry
ansible_ssh_sudo_pass=raspberry
```

Then, edit [`startup.sh`](/torao/iVR/tree/main/files/bin/startup.sh) to specify the options that
fit your environment.

### Run Ansible Playbook

Run the Ansible Playbook to set it up. At this time, run the Ansible with the USB storage device
used for iVR recording installed.

```
$ ansible-playbook -i hosts site.yml
```

## System Structure

![system-boundary](https://user-images.githubusercontent.com/836654/152196050-de549dc6-e55d-4c96-9122-d0dfad279cec.png)

## License

[MIT License](/torao/iVR/tree/main/LICENSE)
