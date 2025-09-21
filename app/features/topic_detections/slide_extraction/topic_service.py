from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid
import os
from supabase import create_client, Client

from app.Core.config import get_settings


class SlideExtractionTopicService:
    def __init__(self):
        settings = get_settings()
        # Prefer service role key server-side to bypass RLS issues
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        self.supabase: Client = create_client(
            settings.supabase_url,
            key
        )

    async def get_topics_from_slide_extraction(self, slide_stack_id: int) -> List[str]:
        """Fetch topics from slide_extraction table for a given slide_stack_id.

        Args:
            slide_stack_id: The ID of the slide stack to get topics for

        Returns:
            List of topic strings extracted from the slide_extraction records
        """
        try:
            response = self.supabase.table("slide_extractions").select(
                "detected_topic, detected_subtopics"
            ).eq("id", slide_stack_id).execute()

            if not response.data:
                return []

            topics = []
            for record in response.data:
                # Add main detected topic
                if record.get("detected_topic"):
                    topics.append(record["detected_topic"])

                # Add detected subtopics
                if record.get("detected_subtopics"):
                    if isinstance(record["detected_subtopics"], list):
                        topics.extend(record["detected_subtopics"])
                    elif isinstance(record["detected_subtopics"], str):
                        # If stored as JSON string, try to parse
                        try:
                            import json
                            subtopics = json.loads(record["detected_subtopics"])
                            if isinstance(subtopics, list):
                                topics.extend(subtopics)
                        except:
                            pass

            return list(set(topics))  # Remove duplicates
        except Exception as e:
            print(f"Error fetching topics from slide_extraction: {e}")
            return []

    async def get_subtopics_for_week(self, week_number: int, module_code: Optional[Any] = None) -> List[str]:
        """Fetch subtopics from the topics table for a given week (and optional module).

        Tries common table names and module columns, returns a de-duplicated list of subtopic strings.
        """
        table_candidates = ["topic", "topics"]
        module_columns = ["module_code", "module", "module_id"]
        for table_name in table_candidates:
            try:
                base = self.supabase.table(table_name).select("week, slug, title, subtopics")
                rows: List[Dict[str, Any]] = []

                if module_code is not None:
                    for col in module_columns:
                        try:
                            resp = base.eq("week", week_number).eq(col, str(module_code)).execute()
                            rows = resp.data or []
                            if rows:
                                break
                        except Exception:
                            continue
                    if not rows:
                        # Fallback to week-only
                        try:
                            resp = base.eq("week", week_number).execute()
                            rows = resp.data or []
                        except Exception:
                            rows = []
                else:
                    resp = base.eq("week", week_number).execute()
                    rows = resp.data or []

                if not rows:
                    continue

                topics: List[str] = []
                for r in rows:
                    subs = r.get("subtopics")
                    if isinstance(subs, list):
                        topics.extend([s for s in subs if isinstance(s, str)])
                    elif isinstance(subs, str):
                        try:
                            import json
                            parsed = json.loads(subs)
                            if isinstance(parsed, list):
                                topics.extend([s for s in parsed if isinstance(s, str)])
                        except Exception:
                            pass

                if not topics:
                    # Fallback to title and slug tokens
                    for r in rows:
                        if isinstance(r.get("title"), str) and r["title"]:
                            topics.append(r["title"])
                        if isinstance(r.get("slug"), str) and r["slug"]:
                            topics.append(r["slug"])

                # De-duplicate preserving order
                seen = set()
                unique_topics: List[str] = []
                for t in topics:
                    if t not in seen:
                        seen.add(t)
                        unique_topics.append(t)
                return unique_topics
            except Exception:
                # Try next table candidate
                continue
        return []

    async def resolve_module_code(self, module_id: Any) -> Optional[str]:
        """Resolve a module_code from a modules table by numeric/text id, if possible.

        Tries common table/column names. Returns None if not resolvable.
        """
        table_candidates = ["modules", "module"]
        code_columns = ["code", "module_code"]
        for table_name in table_candidates:
            try:
                base = self.supabase.table(table_name)
                # Try id column names
                id_cols = ["id", "module_id"]
                for id_col in id_cols:
                    try:
                        resp = base.select("*\n").eq(id_col, module_id).limit(1).execute()
                        rows = resp.data or []
                        if not rows:
                            continue
                        row = rows[0]
                        for cc in code_columns:
                            code_val = row.get(cc)
                            if isinstance(code_val, str) and code_val.strip():
                                return code_val.strip()
                    except Exception:
                        continue
            except Exception:
                continue
        return None

    async def get_slide_extraction_by_week(self, week_number: int, module_id: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get all slide extractions for a specific week and optional module.

        Args:
            week_number: The week number to filter by
            module_id: Optional module ID to filter by

        Returns:
            List of slide extraction records
        """
        try:
            base = (
                self.supabase
                .table("slide_extractions")
                .select("id, module_id, week_number, detected_topic, detected_subtopics")
                .eq("week_number", week_number)
            )

            # Try filtering by different possible module columns; fall back to week-only
            if module_id is not None:
                candidates = [
                    ("module_code", str(module_id)),
                    ("module_id", module_id),
                ]
                for col, val in candidates:
                    try:
                        resp = base.eq(col, val).execute()
                        return resp.data if getattr(resp, "data", None) else []
                    except Exception:
                        continue

            # Fallback: only week filter
            response = base.execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching slide extractions for week {week_number}: {e}")
            return []

    async def get_all_topics_for_week(self, week_number: int, module_id: Optional[Any] = None) -> List[str]:
        """Get all unique topics for a specific week.

        Args:
            week_number: The week number
            module_id: Optional module ID

        Returns:
            List of unique topic strings
        """
        slide_extractions = await self.get_slide_extraction_by_week(week_number, module_id)

        all_topics = []
        for extraction in slide_extractions:
            # Add main detected topic
            if extraction.get("detected_topic"):
                all_topics.append(extraction["detected_topic"])

            # Add detected subtopics
            if extraction.get("detected_subtopics"):
                if isinstance(extraction["detected_subtopics"], list):
                    all_topics.extend(extraction["detected_subtopics"])
                elif isinstance(extraction["detected_subtopics"], str):
                    # If stored as JSON string, try to parse
                    try:
                        import json
                        subtopics = json.loads(extraction["detected_subtopics"])
                        if isinstance(subtopics, list):
                            all_topics.extend(subtopics)
                    except:
                        pass

        return list(set(all_topics))  # Remove duplicates

    async def get_topics_for_module_week(self, module_id: Any, week_number: int) -> List[str]:
        """Exact query: select topics for given module and week number.

    Mirrors: SELECT detected_topic, detected_subtopics FROM slide_extractions
         WHERE module_code = $1 AND week_number = $2;
        """
        try:
            # Try module filters across common column names; fall back to week-only
            rows: List[Dict[str, Any]] = []
            base = self.supabase.table("slide_extractions").select("detected_topic, detected_subtopics")

            candidates = [
                ("module_code", str(module_id)),
                ("module_id", module_id),
            ]
            for col, val in candidates:
                try:
                    resp = base.eq(col, val).eq("week_number", week_number).execute()
                    rows = resp.data or []
                    # If we got rows or no error, break regardless to avoid multiple round-trips
                    if rows:
                        break
                except Exception:
                    continue

            if not rows:
                # As a last resort, fetch by week only
                try:
                    resp = base.eq("week_number", week_number).execute()
                    rows = resp.data or []
                except Exception:
                    rows = []

            topics: List[str] = []
            for row in rows:
                if row.get("detected_topic"):
                    topics.append(row["detected_topic"])
                ds = row.get("detected_subtopics")
                if ds:
                    if isinstance(ds, list):
                        topics.extend(ds)
                    elif isinstance(ds, str):
                        try:
                            import json
                            arr = json.loads(ds)
                            if isinstance(arr, list):
                                topics.extend(arr)
                        except:
                            pass
            return list(set(topics))
        except Exception as e:
            print(f"Error fetching topics for module {module_id}, week {week_number}: {e}")
            return []


# Global instance
slide_extraction_topic_service = SlideExtractionTopicService()