"""
attila.resources
================

Resource usage statistics.
"""

import wmi


from .utility import only


__author__ = 'Nick Denman'


def get_cpu_usage():
    """
    Return the percentage processor usage, as an int, of each processor for the machine running the
    script that called this function.

    :return: The processor usage percentages, as a list of integers.
    """

    return [int(round(cpu.PercentProcessorTime))
            for cpu in wmi.WMI().Win32_PerfFormattedData_PerfOS_Processor()]


def get_ram_usage():
    """
    Return the percentage of RAM usage, as an int, for the machine running the script that called
    this function.

    :return: The RAM usage, as an integer.
    """

    return only(int(round(100 * (1 - ram.FreePhysicalMemory / ram.TotalVisibleMemorySize)))
                for ram in wmi.WMI().Win32_OperatingSystem())


def get_disk_usage(drive_letter='C:'):
    """
    Return the percentage disk usage, as an int.

    :param drive_letter: The drive letter to check.
    :return: The disk usage for the indicated drive.
    """

    if not drive_letter.endswith(':'):
        drive_letter += ':'
    drive_letter = drive_letter.upper()

    # noinspection SqlDialectInspection,SqlNoDataSourceInspection
    return only(int(round(100 * (1 - hdd.FreeSpace / hdd.Size)))
                for hdd in wmi.WMI().query("Select * from Win32_LogicalDisk where DriveType=3")
                if hdd.Caption.upper() == drive_letter)


def get_io_latency(drive_letter='C:'):
    """
    Return the disk latency as a tuple of the form (read_latency, write_latency, transfer_latency).

    :param drive_letter: The drive letter to check.
    :return: The disk usage for the indicated drive, as a tuple (read_latency, write_latency,
        transfer_latency).
    """

    if not drive_letter.endswith(':'):
        drive_letter += ':'
    drive_letter = drive_letter.upper()

    return only((latency.AvgDiskSecPerRead,
                 latency.AvgDiskSecPerWrite,
                 latency.AvgDiskSecPerTransfer)
                for latency in wmi.WMI().Win32_PerfFormattedData_PerfDisk_PhysicalDisk()
                if drive_letter in latency.Name.upper())
