"""
Unit test for get_system_stats telemetry endpoint.
"""

import sys
from pathlib import Path

# Add app directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.chat import get_system_stats


def test_get_system_stats_structure():
    print("Testing get_system_stats structure and fallback capability...")
    stats = get_system_stats()
    assert isinstance(stats, dict), "Stats output is not a dictionary"
    assert "status" in stats, "Missing status key in stats response"
    assert "indexed_vectors" in stats, "Missing indexed_vectors key"
    assert "indexed_vectors_formatted" in stats, "Missing indexed_vectors_formatted key"
    assert "repos_indexed" in stats, "Missing repos_indexed key"
    assert "inference_model" in stats, "Missing inference_model key"
    assert "rag_vector_index" in stats, "Missing rag_vector_index key"
    print(f"Stats output verified: {stats}")
    print("All stats endpoint unit tests PASSED successfully!")


if __name__ == "__main__":
    test_get_system_stats_structure()
