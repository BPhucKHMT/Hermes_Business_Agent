from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
import urllib.parse
import urllib.request
from uuid import uuid4

from tools.calendar.contracts import CalendarEvent, EventDraft


class GoogleCalendarClient:
    def __init__(self, http_client: Any = None) -> None:
        self.http_client = http_client

    def _get_headers(self, token_data: Dict[str, Any]) -> Dict[str, str]:
        token = token_data.get("access_token", "")
        if not token:
            raise ValueError("missing_access_token")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    def _refresh_access_token(self, token_data: Dict[str, Any]) -> str:
        import os
        refresh_token = token_data.get("refresh_token")
        client_id = token_data.get("client_id") or os.environ.get("EMAIL_GOOGLE_CLIENT_ID")
        client_secret = token_data.get("client_secret") or os.environ.get("EMAIL_GOOGLE_CLIENT_SECRET")
        token_uri = token_data.get("token_uri", "https://oauth2.googleapis.com/token")

        if not refresh_token or not client_id or not client_secret:
            return token_data.get("access_token") or token_data.get("token") or ""

        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(token_uri, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                new_token = res.get("access_token", "")
                if new_token:
                    token_data["access_token"] = new_token
                    token_data["token"] = new_token
                    return new_token
        except Exception:
            pass
        return token_data.get("access_token") or token_data.get("token") or ""

    def _request_json(
        self, token_data: Dict[str, Any], url: str, method: str = "GET", body_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        headers = self._get_headers(token_data)
        if self.http_client is not None:
            if method == "GET":
                return self.http_client.get(url, headers=headers)
            elif method == "POST":
                return self.http_client.post(url, headers=headers, body=body_bytes)
            elif method == "DELETE":
                return self.http_client.delete(url, headers=headers)
            return self.http_client.get(url, headers=headers)

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if method == "DELETE":
                    return {"status": resp.status}
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            if err.code == 401:
                new_token = self._refresh_access_token(token_data)
                if new_token and new_token != headers.get("Authorization", "").replace("Bearer ", ""):
                    new_headers = self._get_headers(token_data)
                    retry_req = urllib.request.Request(url, data=body_bytes, headers=new_headers, method=method)
                    with urllib.request.urlopen(retry_req, timeout=15) as resp:
                        if method == "DELETE":
                            return {"status": resp.status}
                        return json.loads(resp.read().decode("utf-8"))
            raise RuntimeError(f"google_calendar_api_error_{err.code}") from err

    def list_events(
        self,
        token_data: Dict[str, Any],
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 50,
    ) -> List[CalendarEvent]:
        if "mock_events" in token_data or token_data.get("mock_mode"):
            events = []
            mock_list = token_data.get("mock_events", [
                {
                    "id": "evt-mock-1",
                    "summary": "Team Sync",
                    "start": {"dateTime": "2026-09-01T10:00:00Z"},
                    "end": {"dateTime": "2026-09-01T11:00:00Z"},
                    "htmlLink": "https://google.com/calendar/event?eid=mock1",
                },
                {
                    "id": "evt-mock-2",
                    "summary": "Client Meeting",
                    "start": {"dateTime": "2026-09-01T14:30:00Z"},
                    "end": {"dateTime": "2026-09-01T15:30:00Z"},
                    "htmlLink": "https://google.com/calendar/event?eid=mock2",
                },
            ])
            for item in mock_list:
                events.append(self._item_to_event(calendar_id, item))
            return events
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
        token_data: Dict[str, Any],
        calendar_id: str,
        event_id: str,
    ) -> CalendarEvent:
        if "mock_events" in token_data or token_data.get("mock_mode"):
            for item in token_data.get("mock_events", []):
                if item.get("id") == event_id:
                    return self._item_to_event(calendar_id, item)
            return CalendarEvent(
                event_id=event_id,
                calendar_id=calendar_id,
                summary="Mock Event",
                description="Mock event description",
                location="Office",
                start_time="2026-09-01T10:00:00Z",
                end_time="2026-09-01T11:00:00Z",
                html_link=f"https://google.com/calendar/event?eid={event_id}",
                status="confirmed",
            )
        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        evt_encoded = urllib.parse.quote(event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events/{evt_encoded}"
        res_data = self._request_json(token_data, url, method="GET")
        return self._item_to_event(calendar_id, res_data)

    def create_event(
        self,
        token_data: Dict[str, Any],
        calendar_id: str,
        draft: EventDraft,
    ) -> CalendarEvent:
        if "mock_events" in token_data or token_data.get("mock_mode"):
            evt_id = f"evt-{uuid4().hex[:16]}"
            link = f"https://www.google.com/calendar/event?eid={evt_id}"
            return CalendarEvent(
                event_id=evt_id,
                calendar_id=calendar_id,
                summary=draft.summary,
                description=draft.description,
                location=draft.location,
                start_time=draft.start_time,
                end_time=draft.end_time,
                html_link=link,
                status="confirmed",
                attendees=draft.attendees,
            )

        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events"
        headers = self._get_headers(token_data)

        payload: Dict[str, Any] = {
            "summary": draft.summary,
            "description": draft.description,
            "location": draft.location,
            "start": {"dateTime": draft.start_time},
            "end": {"dateTime": draft.end_time},
        }
        if draft.attendees:
            payload["attendees"] = [{"email": email} for email in draft.attendees]
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        res_data = self._request_json(token_data, url, method="POST", body_bytes=body_bytes)
        return self._item_to_event(calendar_id, res_data)

    def delete_event(
        self,
        token_data: Dict[str, Any],
        calendar_id: str,
        event_id: str,
    ) -> bool:
        if "mock_events" in token_data or token_data.get("mock_mode"):
            return True

        cal_encoded = urllib.parse.quote(calendar_id, safe="")
        evt_encoded = urllib.parse.quote(event_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_encoded}/events/{evt_encoded}"
        self._request_json(token_data, url, method="DELETE")
        return True

    def _item_to_event(self, calendar_id: str, item: Dict[str, Any]) -> CalendarEvent:
        start_obj = item.get("start", {})
        end_obj = item.get("end", {})
        is_all_day = "date" in start_obj and "dateTime" not in start_obj
        start_time = start_obj.get("dateTime") or start_obj.get("date") or ""
        end_time = end_obj.get("dateTime") or end_obj.get("date") or ""

        attendees = tuple(
            att.get("email", "") for att in item.get("attendees", []) if isinstance(att, dict) and att.get("email")
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
