import unittest
from queue import Queue

import dearpygui.dearpygui as dpg

from logger import LOGGER_HEADER_RESERVE_HEIGHT, Logger


class LoggerTests(unittest.TestCase):
    def testLoggerSyncLayoutKeepsClearButtonCompact(self):
        dpg.create_context()
        try:
            with dpg.window(tag="root"):
                pass
            logger = Logger("root", Queue())
            logger.syncLayout(900, 320)

            filterConfig = dpg.get_item_configuration(logger.filterInputId)
            clearConfig = dpg.get_item_configuration(logger.clearButtonId)
            childConfig = dpg.get_item_configuration(logger.childWindowId)

            self.assertEqual(filterConfig["hint"], "Filter logs")
            self.assertLessEqual(clearConfig["width"], 104)
            self.assertEqual(childConfig["height"], 320 - LOGGER_HEADER_RESERVE_HEIGHT)
        finally:
            dpg.destroy_context()


if __name__ == "__main__":
    unittest.main()
