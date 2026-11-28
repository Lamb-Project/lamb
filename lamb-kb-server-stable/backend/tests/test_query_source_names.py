"""A passage is returned with the name its file was uploaded with (Lamb-Project/lamb#584)."""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Collection, FileRegistry
from services.query import QueryService

STORED = "2fa31972e992455eb39afed5da5c28b2"
OTHER = "bd4b4a0887ba45f695b6eda7c028b9d2"


class SourceNames(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        for cid in (1, 2):
            self.db.add(Collection(id=cid, name=f"c{cid}", owner="7", chromadb_uuid=f"u{cid}", embeddings_model={}))
        self.db.add(FileRegistry(collection_id=1, original_filename="Course guide.pdf", owner="7",
                                 file_path=f"7/c1/{STORED}.pdf", file_url=f"7/c1/{STORED}.pdf", plugin_name="p"))
        self.db.add(FileRegistry(collection_id=2, original_filename="Another collection.pdf", owner="7",
                                 file_path=f"7/c2/{OTHER}.pdf", file_url=f"7/c2/{OTHER}.pdf", plugin_name="p"))
        self.db.commit()

    def named(self, metadata, collection=1):
        results = [{"data": "text", "metadata": metadata}]
        QueryService.name_sources(self.db, collection, results)
        return results[0]["metadata"].get("original_filename")

    def test_the_stored_name_is_matched_with_the_registry(self):
        # As a converted document is stored: the passage points at the converted file.
        self.assertEqual(self.named({"source": f"7/c1/{STORED}.pdf", "filename": f"{STORED}.pdf",
                                     "file_url": f"7/c1/{STORED}.html"}), "Course guide.pdf")
        self.assertEqual(self.named({"file_url": f"7/c1/{STORED}.html"}), "Course guide.pdf")

    def test_a_name_already_there_is_kept_and_an_unknown_file_gets_none(self):
        self.assertEqual(self.named({"filename": f"{STORED}.pdf", "original_filename": "Mine.pdf"}), "Mine.pdf")
        self.assertIsNone(self.named({"filename": "0" * 32 + ".pdf"}))
        self.assertIsNone(self.named({"source_url": "https://example.org/page", "title": "A page"}))

    def test_a_file_of_another_collection_is_never_used(self):
        self.assertIsNone(self.named({"filename": f"{OTHER}.pdf"}, collection=1))
        self.assertEqual(self.named({"filename": f"{OTHER}.pdf"}, collection=2), "Another collection.pdf")

    def test_odd_results_and_a_broken_database_do_not_fail_the_query(self):
        for results in (None, [], [None], [{"data": "x"}], [{"metadata": "x"}]):
            QueryService.name_sources(self.db, 1, results)
        broken = type("Broken", (), {"query": lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no database"))})()
        results = [{"metadata": {"filename": f"{STORED}.pdf"}}]
        QueryService.name_sources(broken, 1, results)
        self.assertNotIn("original_filename", results[0]["metadata"])


if __name__ == "__main__":
    unittest.main()
