from pathlib import Path
import tempfile
import unittest

from km.asset_store import AssetStore


class AssetStoreTests(unittest.TestCase):
    def test_asset_store_initializes_root_and_source_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_root = Path(temp_dir) / "assets"
            store = AssetStore(asset_root)

            source_paths = store.initialize_source("abc123")

            self.assertTrue(asset_root.is_dir())
            self.assertEqual(source_paths.asset_dir, asset_root / "abc123")
            self.assertTrue((asset_root / "abc123" / "raw").is_dir())
            self.assertTrue((asset_root / "abc123" / "canonical").is_dir())
            self.assertTrue((asset_root / "abc123" / "summary").is_dir())
            self.assertEqual(store.index_path, asset_root / "index.sqlite")


if __name__ == "__main__":
    unittest.main()
