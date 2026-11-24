"""
Talos Hardware Control Library

Production-ready wrapper around Talos and Netio hardware.

Author:
    Sascha Märtin

Version:
    1.0.0
"""

from pathlib import Path
from time import sleep
from typing import Optional

from pyvisa import ResourceManager
from Netio import Netio as NetioDevice


class Talos:
    """
    Main Talos automation controller.

    Handles:
        - Talos communication
        - Temperature control
        - Board power control
        - Site readiness monitoring
        - Cache status updates
    """

    CACHE_FILE = "sitestatus.txt"

    def __init__(
        self,
        gpib_address: str = "3",
        netio_url: str = "http://10.62.199.8/netio.json",
        cache_directory: str = "./cache",
    ) -> None:
        self.gpib_address = "GPIB0::"+gpib_address+"::INSTR"
        self.netio_url = netio_url
        self.cache_directory = Path(cache_directory)

        self.instrument = None
        self.netio = None

        self.cache_directory.mkdir(parents=True, exist_ok=True)

    def initialize(self, temp: Optional[float] = None) -> None:
        """
        Initialize instrument and Netio power controller.

        Args:
            temp:
                Target temperature. If None, ambient mode is used.

        Raises:
            ConnectionError:
                If Talos or Netio cannot be reached.
        """

        try:
            rm = ResourceManager()

            self.instrument = rm.open_resource(self.gpib_address)

            self.instrument.read_termination = "\r\n"
            self.instrument.write_termination = "\r\n"
            self.instrument.query_delay = 1
            self.instrument.timeout = None

        except Exception as exc:
            raise ConnectionError(
                f"Unable to connect to Talos: {exc}"
            ) from exc

        try:
            self.netio = NetioDevice(
                self.netio_url,
                auth_rw=("netio", "netio"),
                verify=False,
            )
        except Exception as exc:
            raise ConnectionError(
                f"Unable to connect to Netio: {exc}"
            ) from exc

        self._set_temperature(temp)

        self.power_control(0)

    def _update_cache(self, status: str) -> None:
        """
        Store current site status.
        """

        cache_file = self.cache_directory / self.CACHE_FILE

        with open(cache_file, "w", encoding="utf-8") as file:
            file.write(status)

    def query_site(self) -> bool:
        """
        Query socket readiness.

        Returns:
            True if site is ready.
        """

        status = str(self.instrument.query("CRT?")).strip()

        ready = status == "01"

        self._update_cache("1" if ready else "0")

        return ready

    def power_status(self) -> list[bool]:
        """
        Return current Netio output states.
        """

        outputs = self.netio.get_outputs()

        states = [output.State for output in outputs]

        return states

    def power_control(self, state: int) -> None:
        """
        Control board power.

        Args:
            state:
                0 = OFF
                1 = ON
                2 = TOGGLE

        Raises:
            ValueError:
                Invalid state.
        """

        mapping = {
            0: self.netio.ACTION.OFF,
            1: self.netio.ACTION.ON,
            2: self.netio.ACTION.TOGGLE,
        }

        if state not in mapping:
            raise ValueError("State must be 0, 1 or 2.")

        action = mapping[state]

        for outlet in (1, 2, 3):
            self.netio.set_output(outlet, action)

        sleep(2)

    def handling(self, iteration: int = 0) -> bool:
        """
        Wait until a socket is available and power the board.
        
        Args:
            iteration: 
                when not given start at first position, otherwise take next package
        """

        current_temp = self.instrument.query("TMP?")
        print(f"Current Temperature: {current_temp}")

        if iteration == 0:
            self.instrument.write("RESTART")

        timeout_seconds = 300
        elapsed = 0

        while not self.query_site():
            sleep(2)
            elapsed += 2

            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    "Timeout waiting for site availability."
                )

        self.power_control(1)

        if all(self.power_status()):
            self._update_cache("1")
            return True

        return False

    def _format_temperature(self, temp: float) -> str:
        """
        Build Talos temperature string.
        """

        sign = "+" if temp >= 0 else "-"

        return f"{sign}{abs(temp):06.2f}"

    def _set_temperature(
        self,
        temp: Optional[float],
    ) -> None:

        if temp is None:
            self.instrument.query("TMPM 1,amb")
            return

        self.instrument.query("TMPM 1,tmp")

        command = (
            f"TMP 1,{self._format_temperature(temp)}"
        )

        self.instrument.query(command)

    def temperature_feedback(self) -> float:
        """
        Read current temperature.
        """

        return float(
            self.instrument.query("TMP?")
        )

    def temperature_control(
        self,
        target_temp: float,
    ) -> float:
        """
        Set target temperature and wait for soak.
        """

        soaktime = float(
            self.instrument.query("Soaktime?")
        )

        command = (
            f"TMP 1,{self._format_temperature(target_temp)}"
        )

        self.instrument.query(command)

        sleep(soaktime)

        timeout_seconds = 600
        elapsed = 0

        while not self.query_site():

            sleep(1)
            elapsed += 1

            if elapsed >= timeout_seconds:
                raise TimeoutError(
                    "Temperature stabilization timeout."
                )

        return self.temperature_feedback()

    def end_of_cycle(
        self,
        bin_number: int,
        eot: bool,
    ) -> None:
        """
        End current test cycle.
        """

        self.power_control(0)

        if all(not state for state in self.power_status()):

            self.instrument.write(
                f"01BIN{bin_number:02d}"
            )

            self._update_cache("0")

        if eot:

            self.instrument.query("TMPM 1,amb")
            self.instrument.write("EOCH")

    def safe_shutdown(self) -> None:
        """
        Safely shutdown Talos.
        """

        if any(self.power_status()):

            self.power_control(0)

            sleep(15)

        if any(self.power_status()):
            raise RuntimeError(
                "Unable to switch off power."
            )

        self._update_cache("0")

        self.instrument.query("01BIN31")
        self.instrument.write("EOCH")