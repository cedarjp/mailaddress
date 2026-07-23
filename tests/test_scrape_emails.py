import unittest
from scrape_emails import (
    is_valid_email,
    extract_emails_from_text,
    extract_emails_from_links
)

class TestScrapeEmails(unittest.TestCase):
    def test_is_valid_email(self):
        self.assertTrue(is_valid_email("info@kaigo-example.co.jp"))
        self.assertTrue(is_valid_email("support.center@care-provider.org"))
        
        self.assertFalse(is_valid_email("example@example.com"))
        self.assertFalse(is_valid_email("user@domain.com"))
        self.assertFalse(is_valid_email("icon.png@2x"))

    def test_extract_emails_from_text(self):
        text = """
        お問い合わせはこちらまでお願いいたします。
        E-mail: contact@care-home.jp
        代表メール: info@care-home.jp
        ダミー: test@example.com
        """
        emails = extract_emails_from_text(text)
        self.assertIn("contact@care-home.jp", emails)
        self.assertIn("info@care-home.jp", emails)
        self.assertNotIn("test@example.com", emails)

    def test_extract_emails_from_links(self):
        links = [
            "mailto:info@facility.com?subject=Inquiry",
            "mailto:support@facility.com",
            "http://facility.com/contact"
        ]
        emails = extract_emails_from_links(links)
        self.assertEqual(len(emails), 2)
        self.assertIn("info@facility.com", emails)
        self.assertIn("support@facility.com", emails)

if __name__ == '__main__':
    unittest.main()
