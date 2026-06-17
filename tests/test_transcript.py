import unittest

from summarizer.transcript import extract_video_id

VIDEO_ID = 'dQw4w9WgXcQ'


class TestExtractVideoId(unittest.TestCase):
    def test_watch_url(self):
        self.assertEqual(
            extract_video_id(f'https://www.youtube.com/watch?v={VIDEO_ID}'),
            VIDEO_ID,
        )

    def test_youtu_be(self):
        self.assertEqual(extract_video_id(f'https://youtu.be/{VIDEO_ID}'), VIDEO_ID)

    def test_live_url(self):
        self.assertEqual(
            extract_video_id(f'https://www.youtube.com/live/{VIDEO_ID}'),
            VIDEO_ID,
        )

    def test_shorts_url(self):
        self.assertEqual(
            extract_video_id(f'https://www.youtube.com/shorts/{VIDEO_ID}'),
            VIDEO_ID,
        )

    def test_embed_url(self):
        self.assertEqual(
            extract_video_id(f'https://www.youtube.com/embed/{VIDEO_ID}'),
            VIDEO_ID,
        )

    def test_watch_url_with_extra_query_params(self):
        self.assertEqual(
            extract_video_id(
                f'https://www.youtube.com/watch?feature=share&v={VIDEO_ID}',
            ),
            VIDEO_ID,
        )

    def test_playlist_without_video_id(self):
        self.assertIsNone(
            extract_video_id('https://www.youtube.com/playlist?list=PLxxx'),
        )

    def test_live_url_without_video_id(self):
        self.assertIsNone(extract_video_id('https://www.youtube.com/live/'))

    def test_live_url_not_collapsed_to_garbage_id(self):
        url = f'https://www.youtube.com/live/{VIDEO_ID}'
        self.assertEqual(extract_video_id(url), VIDEO_ID)
        self.assertNotEqual(extract_video_id(url), 'httpswwwyoutubecomli')


if __name__ == '__main__':
    unittest.main()
