import requests
import pandas as pd
import io
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Union, List, Optional
from urllib.parse import quote

class IDEAMDownloader:
    """
    IDEAMDownloader

    Downloader for time series from IDEAM DhimeServicePortal using the
    ConsultarListaSeriesTiempoEstacionesPorFiltroString endpoint.

    Features:
    - Maintains a requests.Session to obtain cookies and reuse connections.
    - Supports chunked downloads (chunk_days) to cover large date ranges.
    - Attempts modern JSON POST that returns a base64-encoded ZIP of CSV files.
    - Provides legacy fallbacks (URL-with-query POST and form-data POST).
    - Post-processes returned CSV into a normalized pandas.DataFrame with:
    - UTC -> local time conversion using tz_offset
    - column renaming (Valor -> value, CodigoEstacion -> station)
    - sorted index by Fecha

    Note on timezone handling:
    - tz_offset is the local offset in hours relative to UTC (Colombia = -5).
    Conversions are applied consistently when building request date strings
    and when converting returned timestamps back to local time.

    Thread-safety / concurrency:
    - The class is not thread-safe as-is because it holds a requests.Session and a
    mutable self.data attribute. Use separate instances in parallel threads.
    """

    BASE_URL = (
        "http://modulopersonalizado.ideam.gov.co/"
        "DhimeServicePortal/api/Listas/ConsultarListaSeriesTiempoEstacionesPorFiltroString"
    )

    PORTAL_HOME = "http://modulopersonalizado.ideam.gov.co/DhimeServicePortal"

    def __init__(self, timezone_offset_hours: int = -5, chunk_days: int = 365):
        """
        Initialize IDEAMDownloader.

        Parameters
        ----------
        timezone_offset_hours : int
            Local timezone offset in hours relative to UTC (example: Colombia = -5).
        chunk_days : int
            Maximum number of days to request per chunk. Smaller values reduce the
            chance of server timeout and memory spikes; 365 or less is recommended.

        Attributes set:
        - self.tz_offset (int): timezone offset hours
        - self.chunk_days (int): chunk size in days
        - self.data (Optional[pd.DataFrame]): storage for last downloaded dataset
        - self.session (requests.Session): persistent HTTP session
        - self.base_headers (dict): default HTTP headers that mimic a browser
        """
        self.tz_offset = timezone_offset_hours
        self.chunk_days = int(chunk_days)
        self.data: Optional[pd.DataFrame] = None
        self.session = requests.Session()


        # Default headers to mimic a browser
        self.base_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/csv, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.PORTAL_HOME,
            "Origin": "http://modulopersonalizado.ideam.gov.co",
            "X-Requested-With": "XMLHttpRequest"
        }

    # -----------------------
    # Internal helpers
    # -----------------------
    def _build_filter(self, stations: List[str], parameter: str, label: str) -> str:
        """
        Construct the server filter expression for multiple stations.

        Parameters
        ----------
        stations : List[str]
            List of station codes to include.
        parameter : str
            Parameter name used by the server (e.g. "PRECIPITACION").
        label : str
            Series label (e.g. "PTPM_CON").

        Returns
        -------
        str
            A filter string that joins single-station predicates with the server's
            "~or~" operator. Caller must ensure values are correctly quoted for the API.
        """
        parts = [
            f"(IdParametro~eq~'{parameter}'~and~Etiqueta~eq~'{label}'~and~IdEstacion~eq~'{st}')"
            for st in stations
        ]
        return "~or~".join(parts)

    def _utc_format(self, dt: datetime) -> str:
        """
        Format a local datetime into the IDEAM UTC timestamp string expected by the API.

        Behavior:
        - Converts a naive or timezone-local datetime using the stored tz_offset
        (utc = local - tz_offset).
        - Produces strings like "YYYY-M-DThh:mm:ss.000Z" (month/day are not zero-padded
        intentionally to match the observed portal format).

        Parameters
        ----------
        dt : datetime
            Local datetime to convert.

        Returns
        -------
        str
            Formatted UTC timestamp string for query parameters.
        """
        # if tz_offset = -5 (Colombia), utc = dt - (-5h) = dt + 5h
        utc_dt = dt - timedelta(hours=self.tz_offset)
        return f"{utc_dt.year}-{utc_dt.month}-{utc_dt.day}T{utc_dt.hour:02d}:{utc_dt.minute:02d}:{utc_dt.second:02d}.000Z"

    def _get_portal(self):
        """
        GET the portal home page to obtain cookies and session state.

        This primes the requests.Session with any cookies or server-side state required
        before making the data POST. Errors are caught and logged (non-fatal).
        """
        try:
            r = self.session.get(self.PORTAL_HOME, headers=self.base_headers, timeout=30)
            print("Portal GET status:", r.status_code)
            # it's okay if 200 or 302, we only need cookies/session
        except requests.RequestException as e:
            print("Warning: portal GET failed:", e)

    def _parse_csv_text(self, text: str) -> pd.DataFrame:
        """
        Parse CSV text into a pandas.DataFrame.

        Returns an empty DataFrame when the input text is empty or only whitespace.

        Parameters
        ----------
        text : str
            Raw CSV text.

        Returns
        -------
        pd.DataFrame
        """
        txt = text.strip()
        if not txt:
            return pd.DataFrame()
        return pd.read_csv(io.StringIO(txt))

    def _stream_text_to_file(self, text: str, out_path: Union[str, Path]) -> None:
        """
        Write CSV text to a file.

        This helper ensures parent folders exist and writes using UTF-8 encoding.

        Parameters
        ----------
        text : str
            CSV content text to write.
        out_path : Union[str, Path]
            Output file path.
        """
        """Save CSV text to file (used when response returns full text)."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def _request_chunk(self, stations: List[str], start: datetime, end: datetime, parameter: str, label: str, stream_to: Optional[Path] = None) -> pd.DataFrame:
        """
        Request a single date chunk for the given stations and series descriptor.

        This method attempts the browser-like JSON POST first and handles:
        - JSON reply containing a base64-encoded ZIP of CSV files (preferred path).
        - JSON error messages from the server (logged and result in empty DataFrame).
        - Raw CSV response fallback.

        It prints diagnostic information (HTTP status, content-type, sizes) to help
        with debugging in interactive runs.

        Parameters
        ----------
        stations : List[str]
            List of station codes.
        start : datetime
            Local start datetime for the chunk.
        end : datetime
            Local end datetime for the chunk.
        parameter : str
            Parameter identifier for the series (e.g. "PRECIPITACION").
        label : str
            Series label (e.g. "PTPM_CON").
        stream_to : Optional[Path]
            If set, the method will save the returned zip or CSV to this path
            (zip suffix is applied automatically for ZIP payloads).

        Returns
        -------
        pd.DataFrame
            Concatenated DataFrame for all CSV files in the returned ZIP, or parsed
            DataFrame for raw CSV. Returns empty DataFrame on errors or unknown formats.

        Notes / edge cases
        - The function accepts an optional self.auth_token attribute. If present it is
        sent as a Bearer token in the Authorization header.
        - UTF-8 is attempted first when decoding CSV files inside ZIP; falls back to
        latin1 on UnicodeDecodeError.
        - Large responses are loaded into memory; for very large downloads consider
        using stream_to and the legacy stream writer function.
        """
        # ensure session cookies from portal
        self._get_portal()

        # Build query-string params (as seen in DevTools)
        params_qs = {
            "sort": "",
            "filter": self._build_filter(stations, parameter, label),
            "group": "",
            "fechaInicio": self._utc_format(start),
            "fechaFin": self._utc_format(end),
            "mostrarGrado": "true",
            "mostrarCalificador": "true",
            "mostrarNivelAprobacion": "true",
            "tipoReporte": "csv"
        }
        qs_parts = [f"{k}={quote(str(v), safe='')}" for k, v in params_qs.items()]
        url_with_qs = f"{self.BASE_URL}?{'&'.join(qs_parts)}"

        # Build JSON payload that the browser sent (example from your cURL)
        # Keep the same structure — server expects an array of series descriptors.
        series_descriptor = [{
            "IdParametro": parameter,
            "Etiqueta": label,
            "EsEjeY1": False,
            "EsEjeY2": False,
            "EsTipoLinea": False,
            "EsTipoBarra": False,
            "TipoSerie": "Estandard",
            "Calculo": ""
        }]

        # Headers similar to browser; include Authorization if provided
        headers = self.base_headers.copy()
        headers["Content-Type"] = "application/json"
        # Use the portal origin used in the browser (dhime.ideam.gov.co)
        headers["Origin"] = "http://dhime.ideam.gov.co"
        headers["Referer"] = self.PORTAL_HOME

        if getattr(self, "auth_token", None):
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # Try: POST with JSON body (this matches the browser cURL you pasted)
        # replace the JSON POST block in _request_chunk with this diagnostic block
        try:
            resp = self.session.post(
                url_with_qs,
                json=series_descriptor,
                headers=headers,
                timeout=180,
                stream=False
            )

            print("JSON POST status:", resp.status_code)
            ctype = resp.headers.get("Content-Type", "<no content-type>")
            clen = resp.headers.get("Content-Length", "<no length>")
            print(f"Response Content-Type: {ctype}; Content-Length: {clen}")

            body_text = resp.text

            import json, base64, zipfile, io

            # ---------------------------------------------------------
            # CASE 1 — IDEAM RETURNS JSON WITH BASE64 ZIP (NORMAL CASE)
            # ---------------------------------------------------------
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = None

            if body_json and isinstance(body_json, dict) and body_json.get("zip"):

                print("Detected ZIP payload from IDEAM")

                try:
                    zip_bytes = base64.b64decode(body_json["zip"])
                except Exception as e:
                    print("Base64 decode failed:", e)
                    return pd.DataFrame()

                # Save zip if requested
                if stream_to:
                    zip_path = Path(stream_to).with_suffix(".zip")
                    zip_path.parent.mkdir(parents=True, exist_ok=True)
                    zip_path.write_bytes(zip_bytes)
                    print("Saved zip to:", zip_path)

                # Open ZIP in memory
                zip_buffer = io.BytesIO(zip_bytes)

                try:
                    with zipfile.ZipFile(zip_buffer) as zf:

                        names = zf.namelist()
                        print("ZIP content:", names)

                        csv_files = [n for n in names if n.lower().endswith(".csv")]

                        if not csv_files:
                            print("ZIP had no CSV files")
                            return pd.DataFrame()

                        frames = []

                        for name in csv_files:
                            with zf.open(name) as f:

                                raw = f.read()

                                try:
                                    df_part = pd.read_csv(io.StringIO(raw.decode("utf-8")))
                                except UnicodeDecodeError:
                                    df_part = pd.read_csv(io.StringIO(raw.decode("latin1")))

                                frames.append(df_part)

                        df_all = pd.concat(frames, ignore_index=True)
                        print("Rows extracted:", len(df_all))
                        return df_all

                except zipfile.BadZipFile:
                    print("Invalid ZIP received")
                    return pd.DataFrame()

            # ---------------------------------------------------------
            # CASE 2 — JSON ERROR MESSAGE FROM SERVER
            # ---------------------------------------------------------
            if body_json is not None:
                print("Server JSON message:", body_json.get("mensaje"))
                return pd.DataFrame()

            # ---------------------------------------------------------
            # CASE 3 — RAW CSV (rare fallback)
            # ---------------------------------------------------------
            if "\n" in body_text and "," in body_text:
                try:
                    df = pd.read_csv(io.StringIO(body_text))
                    print("Parsed raw CSV rows:", len(df))
                    return df
                except Exception as e:
                    print("CSV parse failed:", e)
                    return pd.DataFrame()

            # ---------------------------------------------------------
            # UNKNOWN RESPONSE
            # ---------------------------------------------------------
            print("Unknown response format. First 500 chars:")
            print(body_text[:500])
            return pd.DataFrame()

        except requests.RequestException as e:
            print("HTTP error:", e)
            return pd.DataFrame()


    # add inside class IDEAMDownloader

    def _write_response_stream(self, resp: requests.Response, out_path: Path):
        """
        Stream HTTP response content to a file.

        This is safe for large responses because it writes in chunks.

        Parameters
        ----------
        resp : requests.Response
            Response object with iter_content available.
        out_path : Path
            Destination path for the streamed bytes.

        Returns
        -------
        Path
            The path written to.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
        return out_path

    def _request_chunk_legacy(self, stations: List[str], start: datetime, end: datetime, parameter: str, label: str, stream_to: Optional[Path] = None) -> pd.DataFrame:
        """
        Legacy fallback attempts to download CSV when JSON POST fails.

        Tries two approaches:
        1) POST to URL-with-query (no JSON body). If stream_to is set, the response
        is written to disk and then read by pandas.
        2) POST with application/x-www-form-urlencoded form data to the BASE_URL.

        Parameters
        ----------
        stations, start, end, parameter, label : same as _request_chunk
        stream_to : Optional[Path]
            Optional path to stream response into.

        Returns
        -------
        pd.DataFrame

        Raises
        ------
        RuntimeError
            In the event of a non-network legacy form POST failure with an error snippet.
        """
        params = {
            "sort": "",
            "filter": self._build_filter(stations, parameter, label),
            "group": "",
            "fechaInicio": self._utc_format(start),
            "fechaFin": self._utc_format(end),
            "mostrarGrado": "true",
            "mostrarCalificador": "true",
            "mostrarNivelAprobacion": "true",
            "tipoReporte": "csv"
        }
        # Build URL with encoded qs
        qs_parts = [f"{k}={quote(str(v), safe='')}" for k, v in params.items()]
        url_with_qs = f"{self.BASE_URL}?{'&'.join(qs_parts)}"

        headers_simple = self.base_headers.copy()
        # TRY1: URL-with-query POST
        try:
            resp = self.session.post(url_with_qs, headers=headers_simple, timeout=120, stream=bool(stream_to))
            print("LEGACY TRY1 status:", resp.status_code)
            if resp.status_code == 200:
                if stream_to:
                    return pd.read_csv(self._write_response_stream(resp, Path(stream_to)))
                return self._parse_csv_text(resp.text)
        except requests.RequestException as e:
            print("LEGACY TRY1 exception:", e)

        # TRY2: form-data POST
        headers_form = headers_simple.copy()
        headers_form["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            resp = self.session.post(self.BASE_URL, data=params, headers=headers_form, timeout=120, stream=bool(stream_to))
            print("LEGACY TRY2 status:", resp.status_code)
            if resp.status_code == 200:
                if stream_to:
                    return pd.read_csv(self._write_response_stream(resp, Path(stream_to)))
                return self._parse_csv_text(resp.text)
            else:
                snippet = resp.text[:1000].strip()
                raise RuntimeError(f"Legacy form POST failed {resp.status_code}: {snippet!r}")
        except requests.RequestException as e:
            raise RuntimeError(f"Legacy form POST network error: {e}")
    # -----------------------
    # Public API
    # -----------------------
    def query(self,
              station_code: Union[str, List[str]],
              start_date: Union[str, datetime],
              end_date: Union[str, datetime],
              parameter: str,
              label: str,
              out_chunk_dir: Optional[Union[str, Path]] = None) -> pd.DataFrame:
        """
        Public API: download data for given station(s) and date range.

        The function:
        - normalizes station_code to a list,
        - converts start_date and end_date to pandas timestamps,
        - splits the interval into chunks of up to self.chunk_days days,
        - calls _request_chunk for each chunk and collects results,
        - concatenates frames and calls _postprocess().

        Parameters
        ----------
        station_code : Union[str, List[str]]
            Single station code or list of station codes.
        start_date, end_date : Union[str, datetime]
            Date range for the query (string parseable by pandas.to_datetime).
        parameter : str
            Parameter identifier for the request.
        label : str
            Series label for the request.
        out_chunk_dir : Optional[Union[str, Path]]
            Directory where per-chunk CSVs are saved (useful for large ranges).

        Returns
        -------
        pd.DataFrame
            Combined DataFrame with raw downloaded rows. Sets self.data to the result.

        Raises
        ------
        ValueError
            If end_date is earlier than start_date.
        """
        if isinstance(station_code, str):
            stations = [station_code]
        else:
            stations = list(station_code)

        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        if end < start:
            raise ValueError("end_date must be after start_date")

        frames = []
        current = start
        chunk_idx = 0
        out_chunk_dir = Path(out_chunk_dir) if out_chunk_dir is not None else None

        while current <= end:
            chunk_end = min(current + timedelta(days=self.chunk_days - 1), end)
            print(f"Downloading {current.date()} -> {chunk_end.date()} (chunk {chunk_idx})")
            chunk_file = None
            if out_chunk_dir:
                chunk_file = out_chunk_dir / f"ideam_chunk_{chunk_idx}.csv"
                chunk_file.parent.mkdir(parents=True, exist_ok=True)

            df_chunk = self._request_chunk(stations, current, chunk_end, parameter, label, stream_to=chunk_file)
            if not df_chunk.empty:
                frames.append(df_chunk)
            else:
                print(f"Chunk {chunk_idx} returned no rows.")

            current = chunk_end + timedelta(days=1)
            chunk_idx += 1

        if not frames:
            self.data = pd.DataFrame()
            print("WARNING: no data returned for requested stations/range.")
            return self.data

        self.data = pd.concat(frames, ignore_index=True)
        self._postprocess()
        return self.data

    def _postprocess(self):
        """
        Normalize and clean the combined DataFrame stored in self.data.

        Operations:
        - Parse 'Fecha' column to datetime (coercing errors).
        - Convert timestamps from UTC back to local using tz_offset.
        - Rename columns: 'Valor' -> 'value', 'CodigoEstacion' -> 'station'.
        - Sort by Fecha and reset the index.

        Note: Modifies self.data in place.
        """
        if self.data is None or self.data.empty:
            return

        self.data["Fecha"] = pd.to_datetime(self.data["Fecha"], errors="coerce")

        rename_map = {}
        if "Valor" in self.data.columns:
            rename_map["Valor"] = "value"
        if "CodigoEstacion" in self.data.columns:
            rename_map["CodigoEstacion"] = "station"
        if rename_map:
            self.data = self.data.rename(columns=rename_map)

        self.data = self.data.sort_values("Fecha").reset_index(drop=True)

    def to_timeseries(self, freq: str = "D", agg: str = "sum", fill_missing: bool = True,
                      start: Optional[Union[str, datetime]] = None, end: Optional[Union[str, datetime]] = None) -> pd.DataFrame:
        """
        Resample the downloaded data to a regular time series grouped by station.

        Parameters
        ----------
        freq : str
            Resampling frequency string compatible with pandas (e.g., 'D', 'H').
        agg : str
            Aggregation function name for resampling ('sum', 'mean', etc.).
        fill_missing : bool
            If True, reindex output to a continuous date_range between start and end.
        start, end : Optional[Union[str, datetime]]
            Optional bounds for reindexing; when provided they are interpreted as local
            datetimes and adjusted by tz_offset to construct the index.

        Returns
        -------
        pd.DataFrame
            A DataFrame with columns ['Fecha', 'value', 'station'] resampled per station.

        Raises
        ------
        ValueError
            If no data has been downloaded (self.data is None or empty).
        """
        if self.data is None or self.data.empty:
            raise ValueError("No data downloaded. Run query() first.")

        df = self.data.copy().set_index("Fecha")
        out = []
        for station, g in df.groupby("station"):
            s = g["value"].astype(float).resample(freq).agg(agg)
            if fill_missing:
                if start is None:
                    start_local = s.index.min()
                else:
                    start_local = pd.to_datetime(start) + timedelta(hours=self.tz_offset)
                if end is None:
                    end_local = s.index.max()
                else:
                    end_local = pd.to_datetime(end) + timedelta(hours=self.tz_offset)
                full_idx = pd.date_range(start=start_local, end=end_local, freq=freq)
                s = s.reindex(full_idx)
            s = s.reset_index().rename(columns={"index": "Fecha"})
            s["station"] = station
            out.append(s)
        result = pd.concat(out, ignore_index=True)
        return result

    def export(self, path: Union[str, Path], fmt: str = "csv"):
        """
        Export the normalized in-memory dataset to disk.

        Parameters
        ----------
        path : Union[str, Path]
            Output file path.
        fmt : str
            Output format: 'csv' or 'parquet'. Unsupported formats raise ValueError.

        Raises
        ------
        ValueError
            If self.data is None (no data to export).
        """
        if self.data is None:
            raise ValueError("No data to export. Run query() first.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv":
            self.data.to_csv(path, index=False)
        elif fmt == "parquet":
            self.data.to_parquet(path, index=False)
        else:
            raise ValueError("Unsupported format")

# # -----------------------
# # Example usage (adjust paths and dates as needed)
# # -----------------------
# """
# Example usage block (not executed on import).
# - Instantiate IDEAMDownloader and optionally assign .auth_token.
# - Call query() to download; then to_timeseries() and export().
# Keep auth_token private and do not commit it to source control.
# """

# if __name__ == "__main__":

#     dl = IDEAMDownloader(chunk_days=90)
#     dl.auth_token = "C7XYR1J56B7k-..."   # <- paste the token you saw in DevTools (keep it private)
#     try:
#         df = dl.query(
#             station_code=["17015010"],
#             start_date="1970-01-01",
#             end_date="2025-12-31",
#             parameter="PRECIPITACION",
#             label="PTPM_CON",
#             out_chunk_dir="/.../data/chunks"
#         )
#         print("Rows downloaded:", len(df))
#         ts = dl.to_timeseries(freq="D", start="2019-01-01", end="2019-01-31")
#         print(ts.head())
#         dl.export("/.../data/raw/csv/rain_san_andres.csv")
#         print("Exported CSV")
#     except Exception as e:
#         print("ERROR:", e)