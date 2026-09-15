from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
import urllib.parse
import urllib.request

from tools.calendar.contracts import CalendarEvent, EventDraft


class GoogleCalendarClient:
    def __init__(self, http_client: Any = None) -> None:
        self.http_client = http_client

    def _get_headers(self, token_data: dict[str, Any]) -> dict[str, str]:
        token = token_data.get("access_token", "")
        if not token:
            raise ValueError("missing_access_token")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request_json(
        self,
        token_data: dict[str, Any],
        url: str,
        method: str = "GET",
        body_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        headers = self._get_headers(token_data)
        if self.http_client is not None:
            if method == "GET":
                return self.http_client.get(url, headers=headers)
            elif method == "POST":
                return self.http_client.post(url, headers=headers, body=body_bytes)
            elif method == "DELETE":
                return self.http_client.delete(url, headers=headers)
            return self.http_client.get(url, headers=headers)

        req = urllib.request.Request(
            url, data=body_bytes, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if method == "DELETE":
                    return {"status": resp.status}
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            raise RuntimeError(f"google_calendar_api_error_{err.code}") from err

    def list_events(
        self,
        token_data: dict[str, Any],
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 50,
    ) -> list[CalendarEvent]:
        if "mock_events" in token_data:
            mock_list = token_data.get("mock_events", [])
            return [self._item_to_event(calendar_id, item) for item in mock_list]
        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(max_results),
        }
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max

        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events?{urllib.parse.urlencode(params)}"
        res_data = self._request_json(token_data, url, method="GET")
        items = res_data.get("items", [])
        return [self._item_to_event(calendar_id, item) for item in items]

    def get_event(
        self,
        token_data: dict[str, Any],
        calendar_id: str,
        event_id: str,
    ) -> CalendarEvent:
        if "mock_events" in token_data:
            for item in token_data.get("mock_events", []):
                if item.get("id") == event_id:
                    return self._item_to_event(calendar_id, item)
            if not self.fake_http:
                raise KeyError(f"event_{event_id}_not_found")
        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        evt_encoded = urllib.parse.quote(event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events/{evt_encoded}"
        res_data = self._request_json(token_data, url, method="GET")
        return self._item_to_event(calendar_id, res_data)

    def create_event(
        self,
        token_data: dict[str, Any],
        calendar_id: str,
        draft: EventDraft,
    ) -> CalendarEvent:
        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events"

        payload: dict[str, Any] = {
            "summary": draft.summary,
            "description": draft.description,
            "location": draft.location,
            "start": {"dateTime": draft.start_time},
            "end": {"dateTime": draft.end_time},
        }
        if draft.attendees:
            payload["attendees"] = [{"email": email} for email in draft.attendees]
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        res_data = self._request_json(
            token_data, url, method="POST", body_bytes=body_bytes
        )
        if "mock_events" in token_data and isinstance(res_data, dict):
            token_data["mock_events"].append(res_data)
        return self._item_to_event(calendar_id, res_data)

    def delete_event(
        self,
        token_data: dict[str, Any],
        calendar_id: str,
        event_id: str,
    ) -> bool:

        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        evt_encoded = urllib.parse.quote(event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events/{evt_encoded}"
        self._request_json(token_data, url, method="DELETE")
        return True

    def _item_to_event(self, calendar_id: str, item: dict[str, Any]) -> CalendarEvent:
        start_obj = item.get("start", {})
        end_obj = item.get("end", {})
        is_all_day = "date" in start_obj and "dateTime" not in start_obj
        start_time = start_obj.get("dateTime") or start_obj.get("date") or ""
        end_time = end_obj.get("dateTime") or end_obj.get("date") or ""

        attendees = tuple(
            att.get("email", "")
            for att in item.get("attendees", [])
            if isinstance(att, dict) and att.get("email")
        )

        return CalendarEvent(
            event_id=str(item.get("id", "")),
            calendar_id=calendar_id,
            summary=str(item.get("summary", "")),
            description=str(item.get("description", "")),
            location=str(item.get("location", "")),
            start_time=start_time,
            end_time=end_time,
            html_link=str(item.get("htmlLink", "")),
            status=str(item.get("status", "confirmed")),
            attendees=attendees,
            is_all_day=is_all_day,
        )
