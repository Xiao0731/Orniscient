from __future__ import annotations

try:
    from neo4j_direct_retriever import close_all_drivers, retrieve_kg_context
except ModuleNotFoundError:
    from evaluation.kg_RAG.neo4j_direct_retriever import close_all_drivers, retrieve_kg_context

__all__ = ["retrieve_kg_context", "close_all_drivers"]


if __name__ == "__main__":
    try:
        print(
            retrieve_kg_context(
                target_entity="Whooping Crane",
                question="What are the main habitat and conservation threats of this species?",
                limit=30,
                neighbor_limit=160,
                debug=True,
            )
        )
    finally:
        close_all_drivers()
