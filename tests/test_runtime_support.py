import os
import unittest
from unittest import mock

import runtime_support


class RuntimeSupportTests(unittest.TestCase):
    def testIsFrozenLinuxAppReturnsTrueOnlyForFrozenLinux(self):
        with mock.patch.object(runtime_support.sys, "frozen", True, create=True):
            with mock.patch.object(runtime_support.sys, "platform", "linux"):
                self.assertTrue(runtime_support.isFrozenLinuxApp())

        with mock.patch.object(runtime_support.sys, "frozen", False, create=True):
            with mock.patch.object(runtime_support.sys, "platform", "linux"):
                self.assertFalse(runtime_support.isFrozenLinuxApp())

    def testResolveResourcePathUsesPyInstallerBaseWhenFrozen(self):
        with mock.patch.object(runtime_support.sys, "frozen", True, create=True):
            with mock.patch.object(runtime_support.sys, "_MEIPASS", "/tmp/colorizer-app", create=True):
                resolvedPath = runtime_support.resolveResourcePath("model", "weights.bin")

        self.assertEqual(resolvedPath, "/tmp/colorizer-app/model/weights.bin")

    def testConfigureProcessIdentityCallsSetProcessTitleWhenAvailable(self):
        with mock.patch("runtime_support._setProcessTitle") as setProcessTitleMock:
            with mock.patch("runtime_support._configureLinuxProcessName", return_value=False):
                result = runtime_support.configureProcessIdentity("research-colorizer")

        self.assertTrue(result)
        setProcessTitleMock.assert_called_once_with("research-colorizer")

    def testConfigureProcessIdentityUsesLinuxFallbackWhenSetProcessTitleIsMissing(self):
        with mock.patch("runtime_support._setProcessTitle", None):
            with mock.patch("runtime_support._configureLinuxProcessName", return_value=True) as linuxFallbackMock:
                result = runtime_support.configureProcessIdentity("research-colorizer")

        self.assertTrue(result)
        linuxFallbackMock.assert_called_once_with("research-colorizer")

    def testConfigureProcessIdentityReturnsFalseWhenAllStrategiesFail(self):
        with mock.patch("runtime_support._setProcessTitle", None):
            with mock.patch.object(runtime_support.os, "name", "nt"):
                result = runtime_support.configureProcessIdentity("research-colorizer")

        self.assertFalse(result)

    def testGetAppBaseDirDefaultsToRepositoryRoot(self):
        self.assertEqual(
            runtime_support.getAppBaseDir(),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )


if __name__ == "__main__":
    unittest.main()
