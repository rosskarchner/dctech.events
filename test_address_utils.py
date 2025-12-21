#!/usr/bin/env python3
import unittest
from address_utils import normalize_address


class TestAddressNormalization(unittest.TestCase):
    """Tests for address normalization function."""

    def test_remove_zip_codes(self):
        """Test that zip codes are removed from addresses."""
        self.assertEqual(
            normalize_address('1630 7th St NW, Washington, DC 20001'),
            '1630 7th St NW, Washington, DC'
        )
        self.assertEqual(
            normalize_address('Arlington, VA 22201'),
            'Arlington, VA'
        )

    def test_remove_extended_zip_codes(self):
        """Test that extended zip codes (ZIP+4) are removed."""
        self.assertEqual(
            normalize_address('Arlington, VA 22201-1234'),
            'Arlington, VA'
        )

    def test_remove_united_states(self):
        """Test that 'United States' is removed from addresses."""
        self.assertEqual(
            normalize_address('1630 7th St NW, Washington, DC 20001, United States'),
            '1630 7th St NW, Washington, DC'
        )
        self.assertEqual(
            normalize_address('Arlington, VA, United States'),
            'Arlington, VA'
        )

    def test_remove_usa(self):
        """Test that 'USA' is removed from addresses."""
        self.assertEqual(
            normalize_address('The White House, 1600 Pennsylvania Avenue NW, Washington, DC 20500, USA'),
            'The White House, 1600 Pennsylvania Avenue NW, Washington, DC'
        )

    def test_remove_us(self):
        """Test that 'US' is removed from addresses."""
        self.assertEqual(
            normalize_address('123 Main St, Arlington, VA 22201, US'),
            '123 Main St, Arlington, VA'
        )

    def test_remove_zip_and_country(self):
        """Test that both zip code and country are removed together."""
        self.assertEqual(
            normalize_address('Arlington, VA 22201, United States'),
            'Arlington, VA'
        )

    def test_simple_address_unchanged(self):
        """Test that addresses without zip or country remain unchanged."""
        self.assertEqual(
            normalize_address('Some Place, 123 Main St, Arlington, VA'),
            'Some Place, 123 Main St, Arlington, VA'
        )

    def test_single_part_address(self):
        """Test that single-part addresses are unchanged."""
        self.assertEqual(
            normalize_address('Online Event'),
            'Online Event'
        )

    def test_none_input(self):
        """Test that None input returns None."""
        self.assertIsNone(normalize_address(None))

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        self.assertEqual(normalize_address(''), '')

    def test_non_string_input(self):
        """Test that non-string input is returned as-is."""
        self.assertEqual(normalize_address(123), 123)

    def test_consecutive_duplicates_removed(self):
        """Test that consecutive duplicates are removed."""
        self.assertEqual(
            normalize_address('Arlington, Arlington, VA'),
            'Arlington, VA'
        )

    def test_state_abbreviation_duplicates(self):
        """Test that state abbreviation duplicates are removed."""
        self.assertEqual(
            normalize_address('Arlington, VA, VA'),
            'Arlington, VA'
        )

    def test_case_insensitive_country_removal(self):
        """Test that country removal is case-insensitive."""
        self.assertEqual(
            normalize_address('Arlington, VA, united states'),
            'Arlington, VA'
        )
        self.assertEqual(
            normalize_address('Arlington, VA, Usa'),
            'Arlington, VA'
        )


if __name__ == '__main__':
    unittest.main()
