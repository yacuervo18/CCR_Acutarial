import unittest
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import StaleElementReferenceException

from core import descarga_ts


class DescargaHelpersTests(unittest.TestCase):
    @patch("core.descarga_ts.WebDriverWait")
    @patch("core.descarga_ts._get_element")
    def test_click_reacquires_element_after_stale_reference(
        self, get_element, web_driver_wait
    ):
        driver = MagicMock()
        stale_element = MagicMock()
        fresh_element = MagicMock()
        get_element.side_effect = [stale_element, fresh_element]
        clickable = MagicMock()
        clickable.click.side_effect = [
            StaleElementReferenceException(),
            None,
        ]
        web_driver_wait.return_value.until.return_value = clickable

        descarga_ts._click(driver, ("xpath", "//button"))

        self.assertEqual(get_element.call_count, 2)
        self.assertEqual(clickable.click.call_count, 2)

    @patch("core.descarga_ts.WebDriverWait")
    @patch("core.descarga_ts._get_element")
    def test_send_keys_reacquires_element_after_stale_reference(
        self, get_element, web_driver_wait
    ):
        driver = MagicMock()
        stale_element = MagicMock()
        fresh_element = MagicMock()
        get_element.side_effect = [stale_element, fresh_element]
        stale_element.send_keys.side_effect = StaleElementReferenceException()
        web_driver_wait.return_value.until.side_effect = [
            stale_element,
            fresh_element,
        ]

        descarga_ts._send_keys(driver, ("xpath", "//input"), "valor")

        self.assertEqual(get_element.call_count, 2)
        stale_element.clear.assert_called_once_with()
        fresh_element.clear.assert_called_once_with()
        fresh_element.send_keys.assert_called_once_with("valor")


if __name__ == "__main__":
    unittest.main()
