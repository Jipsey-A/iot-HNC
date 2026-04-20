# Copyright 2024 - 2025 Avram Lubkin, All Rights Reserved

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
An INA228 library for MicroPython and compatible environments

The INA228 is an 85V precise power monitor from Texas Instruments
More information can be found at https://www.ti.com/product/INA228
"""

import math

from machine import I2C
import utime


__version__ = '0.1.0'


# pylint: disable=line-too-long,too-few-public-methods
class Register:
    """Register Addresses"""
    CONFIG =                    0x00  # 16 bits RW Configuration
    ADC_CONFIG =                0x01  # 16 bits RW ADC Configuration
    SHUNT_CAL =                 0x02  # 16 bits RW Shunt Calibration
    SHUNT_TEMPCO =              0x03  # 16 bits RW Shunt Temperature Coefficient
    VSHUNT =                    0x04  # 24 bits R  Shunt Differential Voltage Measurement
    VBUS =                      0x05  # 24 bits R  Bus Voltage Measurement
    DIETEMP =                   0x06  # 16 bits R  Internal Die Temperature Measurement
    CURRENT =                   0x07  # 24 bits R  Current Result
    POWER =                     0x08  # 24 bits R  Power Result
    ENERGY =                    0x09  # 40 bits R  Energy Result
    CHARGE =                    0x0A  # 40 bits R  Charge Result
    DIAG_ALRT =                 0x0B  # 16 bits RW Diagnostic Flags and Alert
    SOVL =                      0x0C  # 16 bits RW Shunt Overvoltage Threshold
    SUVL =                      0x0D  # 16 bits RW Shunt Undervoltage Threshold
    BOVL =                      0x0E  # 16 bits RW Bus Overvoltage Threshold
    BUVL =                      0x0F  # 16 bits RW Bus Undervoltage Threshold
    TEMP_LIMIT =                0x10  # 16 bits RW Temperature Over-Limit Threshold
    PWR_LIMIT =                 0x11  # 16 bits RW Power Over-Limit Threshold
    MANUFACTURER_ID =           0x3E  # 16 bits R  Manufacturer ID
    DEVICE_ID =                 0x3F  # 16 bits R  Device ID


class Config:
    """CONFIG Register Fields"""
    RST =                       1 << 15    # RW Setting generates a system reset, the same as at power on
    RSTACC =                    1 << 14    # RW Resets the contents of accumulation registers ENERGY and CHARGE to 0
    CONVDLY =                   0xFF << 6  # RW 8 bits, Delay for initial ADC conversion in steps of 2 ms
    TEMPCOMP =                  1 << 5     # RW Enables temperature compensation of an external shunt
    ADCRANGE =                  1 << 4     # RW Range across IN+ and IN–, 0: ±163.84 mV 1: ± 40.96 mV
    # RESERVED =                0x0F       # R  4 bits, Always unset


class ADCMode:
    """Values for the MODE field of the ADC_CONFIG register"""
    SHUTDOWN =                  0x0  # No conversions
    TRIGGER_VBUS =              0x1  # Triggered bus voltage, single shot
    TRIGGER_VSHUNT =            0x2  # Triggered shunt voltage, single shot
    TRIGGER_VBUS_VSHUNT =       0x3  # Triggered shunt voltage and bus voltage, single shot
    TRIGGER_DIETEMP =           0x4  # Triggered temperature, single shot
    TRIGGER_VBUS_DIETEMP =      0x5  # Triggered temperature and bus voltage, single shot
    TRIGGER_VSHUNT_DIETEMP =    0x6  # Triggered temperature and shunt voltage, single shot
    TRIGGER_ALL =               0x7  # Triggered bus voltage, shunt voltage and temperature, single shot
    STANDBY =                   0x0  # Same as SHUTDOWN
    CONT_VBUS =                 0x9  # Continuous bus voltage only
    CONT_VSHUNT =               0xA  # Continuous shunt voltage only
    CONT_VBUS_VSHUNT =          0xB  # Continuous shunt and bus voltage
    CONT_DIETEMP =              0xC  # Continuous temperature only
    CONT_VBUS_DIETEMP =         0xD  # Continuous bus voltage and temperature
    CONT_VSHUNT_DIETEMP =       0xE  # Continuous temperature and shunt voltage
    CONT_ALL =                  0xF  # Continuous bus voltage, shunt voltage and temperature


class DiagAlert:
    """DIAG_ALERT Register Fields"""
    ALATCH =                    1 << 15  # RW When unset alert pin and flag reset when fault is cleared, when set resets when read
    CNVR =                      1 << 14  # RW When set, alert pin triggers for CNVRF
    SLOWALERT =                 1 << 13  # RW When set alert is delayed until average value is computed
    APOL =                      1 << 12  # RW Alert pin polarity, defaults to unset, active-low, open drain
    ENERGYOF =                  1 << 11  # R  Set when the ENERGY register has overflowed
    CHARGEOF =                  1 << 10  # R  Set when the CHARGE register has overflowed
    MATHOF =                    1 << 9   # R  Set when an arithmetic operation resulted in an overflow
    # RESERVED =                1 << 8   # R  Always unset
    TMPOL =                     1 << 7   # RW Set if temperature exceeds over-limit threshold
    SHNTOL =                    1 << 6   # RW Set if shunt voltage exceeds over-limit threshold
    SHNTUL =                    1 << 5   # RW Set if shunt voltage is below under-limit threshold
    BUSOL =                     1 << 4   # RW Set if bus voltage exceeds over-limit threshold
    BUSUL =                     1 << 3   # RW Set if bus voltage is below under-limit threshold
    POL =                       1 << 2   # RW Set if power exceeds over-limit threshold
    CNVRF =                     1 << 1   # RW Set when conversion is complete
    MEMSTAT =                   1 << 0   # RW Set when a checksum error is detected in trim memory
# pylint: enable=line-too-long,too-few-public-methods


DIAG_ALRT_ERROR_IF_SET = (
    DiagAlert.ENERGYOF | DiagAlert.CHARGEOF | DiagAlert.MATHOF | DiagAlert.TMPOL |
    DiagAlert.SHNTOL | DiagAlert.SHNTUL | DiagAlert.BUSOL | DiagAlert.BUSUL | DiagAlert.POL
)


# ADC Conversion time in µs
CONVERSION_TIME = {
    50:     0x0,
    84:     0x1,
    150:    0x2,
    280:    0x3,
    540:    0x4,
    1052:   0x5,
    2074:   0x6,
    4120:   0x7,
}

# ADC sample averaging count
AVERAGING_COUNT = {
    1:      0x0,
    4:      0x1,
    16:     0x2,
    64:     0x3,
    128:    0x4,
    256:    0x5,
    512:    0x6,
    1024:   0x7,
}


def twos_comp(value, bits):
    """
    If the most significant bit is set, then convert to negative number
    """
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def to_twos_comp(value, bits):
    """
    Clamp value within bit range with most significant set if negative
    """
    value = max(-(1 << (bits - 1)), min(value, (1 << (bits - 1)) - 1))
    return (1 << bits) + value if value < 0 else value


class INA228:  # pylint: disable=too-many-public-methods
    """
    Driver for the Texas Instruments INA228 precision power monitor.

    This class provides an interface for reading voltage, current, power,
    energy, charge, and die temperature measurements over I2C.

    Args:
        i2c (I2C): The I2C bus instance.
        address (int, optional): I2C address of the INA228 device. Defaults to 0x40.
        shunt_resistance (float, optional): Shunt resistor value in ohms. Defaults to 0.015 Ω,
        max_current (float, optional): Maximum expected current in amperes. Defaults to 10 A.

    The default parameters are based on Adafruit product 5832, an INA228 breakout board, which
    which includes a 15mΩ resistor and a max rating of 10A.

    Example:
        sensor = INA228(i2c)
        print(sensor.voltage, sensor.current)
    """

    def __init__(
        self, i2c: I2C, address: int = 0x40, shunt_resistance: float = 0.015, max_current=10
    ):
        self.i2c = i2c
        self.address = address
        self.reset()
        self._adc_range = 0
        self.shunt_cal = 0
        self.current_lsb = 0.0
        self.configure(shunt_resistance, max_current)

    def _write_register_16bit(self, reg, value):
        self.i2c.writeto(
            self.address,
            bytearray([reg, (value >> 8) & 0xFF, value & 0xFF]),
        )

    def _read_register_16bit(self, reg):
        self.i2c.writeto(self.address, bytes([reg]))
        data = self.i2c.readfrom(self.address, 2)
        return (data[0] << 8) | data[1]

    def _read_register_24bit(self, reg):
        self.i2c.writeto(self.address, bytes([reg]))
        data = self.i2c.readfrom(self.address, 3)
        return (data[0] << 16) | (data[1] << 8) | data[2]

    def _read_register_40bit(self, reg):
        self.i2c.writeto(self.address, bytes([reg]))
        data = self.i2c.readfrom(self.address, 5)
        return (data[0] << 32) | (data[1] << 24) | (data[2] << 16) | (data[3] << 8) | data[4]

    def reset(self):
        """
        Reset configuration register
        """
        self._write_register_16bit(Register.CONFIG, Config.RST)
        utime.sleep_ms(2)  # Give time to reset

    def reset_accumulation(self):
        """
        Clear energy and charge registers
        """
        current = self._read_register_16bit(Register.CONFIG)
        self._write_register_16bit(Register.CONFIG, Config.RSTACC | current)
        utime.sleep_ms(2)  # Give time to reset

    def configure(self, shunt_resistance: float, max_current: float):
        """
        Configure INA228 with the provided shunt resistance and expected maximum current.

        This method:
        - Calculates the maximum expected shunt voltage (V = I × R)
        - Automatically selects the ADC range (±40.96 mV or ±163.84 mV)
        - Computes and writes the shunt calibration register (SHUNT_CAL)
        - Stores the calculated current LSB for later current and power calculations

        Parameters:
            shunt_resistance (float): Shunt resistor value in ohms (Ω)
            max_current (float): Maximum expected current in amperes (A)

        Raises:
            ValueError: If the calculated shunt voltage exceeds ADC range or SHUNT_CAL
                        exceeds 15-bit limit
        """

        shunt_max_voltage = max_current * shunt_resistance
        if shunt_max_voltage <= 40.96e-3:  # 40.96 mV
            full_adc = False
        elif shunt_max_voltage <= 163.84e-3:  # 163.84 mV
            full_adc = True
        else:
            raise ValueError('Maximum shut voltage exceeds ADC capacity of 163.84 mV')

        current_lsb = max_current / 0x80000  # 19 bits
        shunt_cal = math.ceil(13107.2e6 * current_lsb * shunt_resistance * (1 if full_adc else 4))
        if shunt_cal > 0x7FFF:
            raise ValueError(
                'Calculated shunt calibration exceeds specification. Verify shunt resistance and max current'
            )

        self.shunt_cal = shunt_cal
        self.current_lsb = current_lsb
        self.power_lsb = current_lsb * 3.2
        self.full_adc_range = full_adc
        self._write_register_16bit(Register.SHUNT_CAL, shunt_cal)
        utime.sleep_ms(2)  # Give time to reset

    def configure_adc(
        self, mode=ADCMode.CONT_ALL, vbusct=CONVERSION_TIME[1052], vshct=CONVERSION_TIME[1052],
        vtct=CONVERSION_TIME[1052], avg=AVERAGING_COUNT[1]
    ):
        """
        Sets the ADC register

        Use constant values to set
        mode: Triggered or continuous mode for bus voltage, shunt voltage, or die temperature
        vbusct: Conversion time of the bus voltage measurement in µs
        vshct: Conversion time of the shunt voltage measurement in µs
        vtct: Conversion time of the temperature measurement in µs
        avg: ADC sample averaging count
        """

        self._write_register_16bit(
            Register.ADC_CONFIG, avg | (vtct << 3) | (vshct << 6) | (vbusct << 9) | (mode << 12)
        )

    def trigger(self, mode: int = ADCMode.TRIGGER_ALL):
        """
        Trigger a read of bus voltage, shunt voltage, and/or temperature
        """

        if mode < 1 or mode > 7:
            raise ValueError('Invalid trigger mode')

        current = self._read_register_16bit(Register.ADC_CONFIG)
        self._write_register_16bit(
            Register.ADC_CONFIG, (current & ~(15 << 12)) | (mode << 12)
        )

    @property
    def convdly(self) -> int:
        """
        Initial ADC conversion delay, CONVDLY in the CONFIG register
        The delay is set in steps of 2 ms (0 - 510 ms). Default is 0.
        """
        return 2 * ((self._read_register_16bit(Register.CONFIG) & Config.CONVDLY) >> 6)

    @convdly.setter
    def convdly(self, value: int):

        if value < 0 or value > 510:
            raise ValueError('Delay must be between 0 and 510 ms.')

        current = self._read_register_16bit(Register.CONFIG)

        # Clear the CONVDLY field (bits 13-6), then set the new value
        new_value = (current & ~(Config.CONVDLY)) | (round(value / 2) << 6)
        self._write_register_16bit(Register.CONFIG, new_value)

        utime.sleep_ms(2)  # Give time to set

    @property
    def tempcomp(self) -> bool:
        """
        Temperature Compensation, TEMPCOMP in the CONFIG register
        """
        return bool(self._read_register_16bit(Register.CONFIG) & Config.TEMPCOMP)

    @tempcomp.setter
    def tempcomp(self, value: bool):
        current = self._read_register_16bit(Register.CONFIG)
        if value:
            self._write_register_16bit(Register.CONFIG, Config.TEMPCOMP | current)
        else:
            self._write_register_16bit(Register.CONFIG, ~Config.TEMPCOMP & current)

        utime.sleep_ms(2)  # Give time to set

    @property
    def full_adc_range(self):
        """
        Works in inverse to ADCRANGE in the CONFIG REGISTER
        If True, set to 0: ±163.84 mV
        If False, set to 1: ± 40.96 mV
        """
        return not bool(self._read_register_16bit(Register.CONFIG) & Config.ADCRANGE)

    @full_adc_range.setter
    def full_adc_range(self, value: bool):
        current = self._read_register_16bit(Register.CONFIG)
        if value:
            self._write_register_16bit(Register.CONFIG, ~Config.ADCRANGE & current)
            self._adc_range = 0
        else:
            self._write_register_16bit(Register.CONFIG, Config.ADCRANGE | current)
            self._adc_range = 1

        utime.sleep_ms(2)  # Give time to set

    @property
    def shunt_tempco(self) -> int:
        """
        Shunt temperature coefficient (SHUNT_TEMPCO) in ppm/°C from 25C

        Only used when Shunt Temperature Compensation (TEMPCOMP) is enabled in the configuration
        Adjusts for resistor variance based on temperature with following formula
        R_adj = R_nom + (R_nom * (DIETEMP - 25) x SHUNT_TEMPCO) / 1e6
        """
        return self._read_register_16bit(Register.SHUNT_TEMPCO) & 0x3FFF

    @shunt_tempco.setter
    def shunt_tempco(self, value: int):
        if value < 0 or value > 16383:
            raise ValueError('Coefficient must be between 0 and 16383 ppm/°C')

        self._write_register_16bit(Register.SHUNT_TEMPCO, value)

    @property
    def shunt_voltage(self) -> float:
        """Shunt Voltage (VSHUNT)"""
        raw = self._read_register_24bit(Register.VSHUNT)
        value = twos_comp((raw >> 4), 20)  # Bits 23-4, signed
        # Conversion factor 312.5 nV/LSB when ADCRANGE = 0
        # Conversion factor 78.125 nV/LSB when ADCRANGE = 1
        return value * (78.125e-9 if self._adc_range else 312.5e-9)

    @property
    def voltage(self) -> float:
        """Bus Voltage (VBUS)"""
        raw = self._read_register_24bit(Register.VBUS)
        # Only using bits 23 - 4 and Conversion factor is 195.3125 µV/LSB
        # Uses two's complement, but is always positive, so skip it
        return (raw >> 4) * 195.3125e-6

    @property
    def temperature(self) -> float:
        """Internal temperature of die in degrees Celsius (DIETEMP)"""
        raw = self._read_register_16bit(Register.DIETEMP)
        # Conversion factor: 7.8125 m°C/LSB
        return twos_comp(raw, 16) * 7.8125e-3

    @property
    def current(self) -> float:
        """Current in Amps (CURRENT)"""
        raw = self._read_register_24bit(Register.CURRENT)
        value = twos_comp((raw >> 4), 20)  # Bits 23-4, signed
        return self.current_lsb * value

    @property
    def power(self) -> float:
        """Power in Watts (POWER)"""
        raw = self._read_register_24bit(Register.POWER)
        return self.power_lsb * raw

    @property
    def energy(self) -> float:
        """Energy in Joules (ENERGY)"""
        raw = self._read_register_40bit(Register.ENERGY)
        return 16 * self.power_lsb * raw

    @property
    def charge(self) -> float:
        """Charge in Coulombs (CHARGE)"""
        raw = self._read_register_40bit(Register.CHARGE)
        return self.current_lsb * twos_comp(raw, 40)

    @property
    def manufacturer_id(self) -> str:
        """Manufacturer ID (MANUFACTURER_ID)"""
        value = self._read_register_16bit(Register.MANUFACTURER_ID)
        # Convert to ASCII characters. Should be TI
        return chr((value >> 8) & 0xFF) + chr(value & 0xFF)

    @property
    def device_id(self) -> str:
        """Returns device ID as string with format ID.REVISION (DEVICE_ID)"""
        value = self._read_register_16bit(Register.DEVICE_ID)
        # Bits 15-4 are the ID, should be 0x228
        # Bits 3-0 are the revision
        return f'{(value >> 4) & 0x0FFF:X}.{value & 0x0F}'

    @property
    def alert(self) -> int:
        """DIAG_ALRT Register"""
        return self._read_register_16bit(Register.DIAG_ALRT)

    @alert.setter
    def alert(self, value):
        self._write_register_16bit(Register.DIAG_ALRT, value)

    @property
    def sovl(self) -> float:
        """Shunt overvoltage threshold (SOVL)"""
        raw = self._read_register_16bit(Register.SOVL)
        return twos_comp(raw, 16) * (1.25e-6 if self._adc_range else 5e-6)

    @sovl.setter
    def sovl(self, value):
        scale_factor = 1.25e-6 if self._adc_range else 5e-6
        max_value = 0x7FFF * scale_factor
        min_value = -0x8000 * scale_factor

        if value < min_value or value > max_value:
            raise ValueError(
                f'In the current configuration, the threshold must be between {min_value} and {max_value} Volts'
            )

        value = round(value / scale_factor)
        self._write_register_16bit(Register.SOVL, to_twos_comp(value, 16))

    @property
    def suvl(self) -> float:
        """Shunt undervoltage threshold (SUVL)"""
        raw = self._read_register_16bit(Register.SUVL)
        return twos_comp(raw, 16) * (1.25e-6 if self._adc_range else 5e-6)

    @suvl.setter
    def suvl(self, value):
        scale_factor = 1.25e-6 if self._adc_range else 5e-6
        max_value = 0x7FFF * scale_factor
        min_value = -0x8000 * scale_factor

        if value < min_value or value > max_value:
            raise ValueError(
                f'In the current configuration, the threshold must be between {min_value} and {max_value} Volts'
            )

        self._write_register_16bit(Register.SUVL, to_twos_comp(round(value / scale_factor), 16))

    @property
    def bovl(self) -> float:
        """Bus overvoltage threshold (BOVL)"""
        raw = self._read_register_16bit(Register.BOVL)
        return (raw & 0x7FFF) * 3.125e-3

    @bovl.setter
    def bovl(self, value):
        max_value = 0x7FFF * 3.125e-3
        if value < 0 or value > max_value:
            raise ValueError(f'Threshold must be between 0 and {max_value} Volts')

        value = min(round(abs(value / 3.125e-3)), 0x7FFF)
        self._write_register_16bit(Register.BOVL, value)

    @property
    def buvl(self) -> float:
        """Bus undervoltage threshold (BUVL)"""
        raw = self._read_register_16bit(Register.BUVL)
        return (raw & 0x7FFF) * 3.125e-3

    @buvl.setter
    def buvl(self, value):
        max_value = 0x7FFF * 3.125e-3
        if value < 0 or value > max_value:
            raise ValueError(f'Threshold must be between 0 and {max_value} Volts')

        value = min(round(abs(value / 3.125e-3)), 0x7FFF)
        self._write_register_16bit(Register.BUVL, value)

    @property
    def temp_limit(self) -> float:
        """Temperature over-limit threshold in degrees Celsius (TEMP_LIMIT)"""
        return twos_comp(self._read_register_16bit(Register.TEMP_LIMIT), 16) * 7.8125e-3

    @temp_limit.setter
    def temp_limit(self, value: float):
        max_value = 0x7FFF * 7.8125e-3
        if value < -256 or value > max_value:
            raise ValueError(f'Threshold must be between -256 and {max_value} °C')

        value = round(value / 7.8125e-3)
        self._write_register_16bit(Register.TEMP_LIMIT, to_twos_comp(value, 16))

    @property
    def pwr_limit(self) -> float:
        """Power over-limit threshold in Watts {PWR_LIMIT}"""
        return self._read_register_16bit(Register.PWR_LIMIT) * self.power_lsb * 256

    @pwr_limit.setter
    def pwr_limit(self, value: float):

        scale_factor = self.power_lsb * 256
        max_value = 0xFFFF * scale_factor

        if value < 0 or value > max_value:
            raise ValueError(
                f'In the current configuration, power limit must be between 0 and {max_value} W'
            )

        value = min(round(abs(value / scale_factor)), 0xFFFF)
        self._write_register_16bit(Register.PWR_LIMIT, value)


