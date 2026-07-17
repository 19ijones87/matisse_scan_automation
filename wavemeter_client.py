"""
wavemeter_client.py

Reads laser frequency from a HighFinesse wavemeter, via the official
wlmData.dll wrapper (wlmData.py / wlmConst.py). Windows-only, since it
loads a Windows DLL through ctypes.WinDLL -- must be run on the TiSa PC,
not on a development machine like macOS/Linux.

Author: A. Halil Ceylan
        Koç University, Istanbul - LENS, Florence

Last updated: 2026-07-17
"""

import wlmConst
import wlmData

wlmData.LoadDLL("C:\\WINDOWS\\system32\\wlmData.dll")

def get_frequency(channel):
    frequency = wlmData.dll.GetFrequencyNum(channel, 0.0)

    if (frequency == wlmConst.ErrWlmMissing):
        raise RuntimeError("WLM software not reachable (channel {})".format(channel))
    
    if(frequency <= 0):
        return None
    return frequency
        

def calculate_statistics(frequencies):
    if(len(frequencies) == 0):
        raise RuntimeError("No valid readings!!!")
    
    avg = sum(frequencies) / len(frequencies)
    span = max(frequencies) - min(frequencies)

    return avg,span

