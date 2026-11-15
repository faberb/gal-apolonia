import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from import_wordpress import SafeContent, image_source_path, parse_sql_values


class ImportWordPressTests(unittest.TestCase):
    def test_parse_sql_values_unescapes_strings_and_keeps_commas(self) -> None:
        self.assertEqual(
            parse_sql_values(r"(1, 'line\nnext', 'O\'Brien', 'a,b');"),
            ["1", "line\nnext", "O'Brien", "a,b"],
        )

    def test_upload_path_is_relative_to_wordpress_uploads(self) -> None:
        self.assertEqual(
            image_source_path(
                "https://galapolonia.com/wp-content/uploads/2020/04/trail%20photo.jpg"
            ),
            "2020/04/trail photo.jpg",
        )
        self.assertIsNone(image_source_path("https://example.com/photo.jpg"))

    def test_sanitizer_rewrites_images_and_keeps_bracketed_copy(self) -> None:
        media = {"2020/04/trail.jpg": "assets/images/posts/trail.jpg"}
        sanitizer = SafeContent(media, {}, {})

        result = sanitizer.clean(
            '<p>Snow [on the trail].</p>'
            '<figure><img src="https://galapolonia.com/wp-content/uploads/'
            '2020/04/trail.jpg" alt="Trail">'
            "<figcaption>Above the clouds</figcaption></figure>"
        )

        self.assertIn("Snow [on the trail].", result)
        self.assertIn('src="assets/images/posts/trail.jpg"', result)
        self.assertIn('loading="lazy"', result)
        self.assertIn("<figcaption>Above the clouds</figcaption>", result)

    def test_sanitizer_drops_scripts_and_unsafe_links(self) -> None:
        sanitizer = SafeContent({}, {}, {})
        result = sanitizer.clean(
            '<p>Story <a href="javascript:alert(1)">link</a></p>'
            "<script>unsafe()</script>"
        )

        self.assertEqual(result, "<p>Story <a>link</a></p>")
        self.assertNotIn("unsafe()", result)


if __name__ == "__main__":
    unittest.main()
