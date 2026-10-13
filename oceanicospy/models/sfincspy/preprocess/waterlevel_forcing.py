import os
from typing import Optional

import pandas as pd
import geopandas as gpd
from hydromt_sfincs import SfincsModel, utils as hydromt_utils

from .... import utils as oceanicospy_utils
from ....utils.waterlevel import download_uhslc_waterlevel, load_uhslc_waterlevel
from ....analysis.harmonic_tides import tide_harmonic_decomposition


class WaterLevelForcing:
    """
    Generador de forzante de nivel del mar (bzs) para SFINCS.

    Sigue la misma convención que
    ``xbeachpy.preprocess.WaterLevelForcing``: esta clase solo se encarga
    de obtener/leer los datos y de escribirlos en el formato que necesita
    el modelo. **No aplica ninguna corrección de datum** - igual que en
    XBeach, cualquier corrección específica de estación (p. ej. el ajuste
    de -2.0 m para fechas <= 2018-12-31 en la estación UHSLC 737 de San
    Andrés, ya usado en los ``main_xbeach.py`` de este proyecto) debe
    aplicarse en el script del caso, sobre el DataFrame devuelto por
    :meth:`get_waterlevel_from_UHSLC`, antes de pasarlo a
    :meth:`from_dataframe`.

    Parameters
    ----------
    model : SfincsModel
        Instancia del modelo SFINCS inicializada con HydroMT.

    Notes
    -----
    - El archivo generado es utilizado como forzante de nivel del mar (`bzs`).
    - Se crea automáticamente la geometría de frontera (`bnd`) en el punto
      dado.
    """

    def __init__(self, model: SfincsModel) -> None:
        self.model = model

    # --------------------------------------------------
    # OBTENCIÓN DE DATOS CRUDOS (sin corrección de datum)
    # --------------------------------------------------
    def get_waterlevel_from_UHSLC(
        self,
        station_id,
        input_dir: str,
        override: bool = False,
    ) -> pd.DataFrame:
        """
        Obtiene datos crudos de nivel del mar de UHSLC, descargando solo
        cuando hace falta - mismo comportamiento que
        ``xbeachpy.preprocess.WaterLevelForcing.get_waterlevel_from_UHSLC``.

        Reutiliza el mismo downloader compartido
        (``oceanicospy.utils.waterlevel``), así que el archivo crudo
        (``h<station_id>.csv``) y el DataFrame resultante son idénticos a
        los que usa XBeach para la misma estación.

        Parameters
        ----------
        station_id : str or int
            Código de estación UHSLC (p. ej. ``737``).
        input_dir : str
            Carpeta ``input/`` del caso, donde se guarda/busca
            ``h<station_id>.csv``.
        override : bool, optional
            Si es True, vuelve a descargar aunque el archivo ya exista.

        Returns
        -------
        pandas.DataFrame
            DataFrame crudo con índice de tiempo (hora local, UTC-5) y
            columna ``depth[m]``. **Sin corrección de datum** - ver la
            nota de clase.
        """
        filepath = f"{input_dir}h{station_id}.csv"
        file_exists = oceanicospy_utils.verify_file(filepath)

        if not file_exists or override:
            tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
            tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])
            return download_uhslc_waterlevel(station_id, tstart, tstop, filepath)

        print("\t UHSLC water level data already exists, skipping download")
        return load_uhslc_waterlevel(station_id, filepath)

    # --------------------------------------------------
    # DESCOMPOSICIÓN ARMÓNICA (marea astronómica pura)
    # --------------------------------------------------
    def to_astronomical_tide(
        self,
        df: pd.DataFrame,
        column_name: str,
        lat: float = 12.57,
        method: str = "ols",
        out_column: str = "tide[m]",
        min_plausible_value: Optional[float] = -10.0,
    ) -> pd.DataFrame:
        """
        Descompone una serie de nivel del mar ya preparada en su
        componente puramente astronómica, vía análisis armónico (UTide),
        quitando el residual meteorológico/storm surge real de esa fecha.

        Pensado para el caso "P" (pluvial-only) del esquema C/P/CP: usar
        el nivel del mar total observado como frontera de marea de "P"
        dejaría filtrar el residual meteorológico real de la fecha del
        evento (varios de estos eventos SON tormentas costeras en la
        definición de otro escenario, p. ej. S1/S4) - justo el mecanismo
        costero que "P" no debe incluir. Ver project memory
        (`project_sfincs_swmm_coupling_option4`) para la discusión
        completa. **No** se usa para C/CP, donde el nivel total observado
        (con su residual) sí corresponde, al ser ese el mecanismo costero
        que se está evaluando.

        El ajuste armónico se hace sobre **todo** el registro dado en
        `df` - debe ser el registro largo multianual (p. ej. el devuelto
        por :meth:`get_waterlevel_from_UHSLC`, sin recortar), no solo la
        ventana corta del evento, para obtener constituyentes robustos.
        Aplica cualquier corrección de datum sobre `df` **antes** de
        llamar a este método (mismo principio que en
        :meth:`from_dataframe`) - un salto de datum sin corregir en medio
        del registro sesgaría el ajuste armónico.

        Parameters
        ----------
        df : pandas.DataFrame
            Serie de nivel del mar ya preparada (índice de tiempo, con
            cualquier corrección de datum ya aplicada), normalmente el
            registro multianual completo.
        column_name : str
            Nombre de la columna de nivel del mar en `df`.
        lat : float, optional
            Latitud de la estación, requerida por UTide para la
            frecuencia de Coriolis. Por defecto 12.57 (San Andrés,
            estación UHSLC 737).
        method : str, optional
            Método de regresión de UTide (ver
            :func:`oceanicospy.analysis.harmonic_tides.tide_harmonic_decomposition`).
            Por defecto ``"ols"``.
        out_column : str, optional
            Nombre de la columna de salida. Por defecto ``"tide[m]"``.
        min_plausible_value : float or None, optional
            Umbral de plausibilidad física (m) para descartar el valor
            centinela de datos faltantes de UHSLC (p. ej. estación 737
            usa ``-32.767``) antes del ajuste armónico - sin esto, ~25%
            del registro de h737.csv queda contaminado y UTide diverge
            (amplitudes sin sentido físico, ver project memory). Se usa
            un umbral ("< min_plausible_value" se descarta) en vez de
            comparar contra el valor centinela exacto porque cualquier
            corrección de datum ya aplicada por quien llama (p. ej. el
            ajuste de -2.0 m de la estación 737) desplaza ese valor
            exacto -- un umbral generoso (-10 m, muy por debajo de
            cualquier nivel del mar real) lo captura de todas formas sin
            necesitar conocer el desplazamiento. Si es ``None``, no se
            aplica ningún filtro.

        Returns
        -------
        pandas.DataFrame
            Índice de tiempo, una columna (`out_column`) con la
            reconstrucción astronómica - lista para pasar a
            :meth:`from_dataframe`.

        Raises
        ------
        ValueError
            Si `column_name` no existe en `df`, o si la serie queda
            vacía tras quitar nulos/valores centinela.
        """
        if column_name not in df.columns:
            raise ValueError(f"No existe columna '{column_name}' en df")

        valid = df[column_name].dropna()
        if min_plausible_value is not None:
            valid = valid[valid > min_plausible_value]
        if valid.empty:
            raise ValueError("La serie quedó vacía tras quitar nulos/valores centinela")

        serie_table, _ = tide_harmonic_decomposition(
            data=valid, time=valid.index, lat=lat, method=method, conf_int="none",
        )
        return (
            serie_table.set_index("time")[["tide"]]
            .rename(columns={"tide": out_column})
        )

    # --------------------------------------------------
    # ESCRITURA DEL FORZANTE
    # --------------------------------------------------
    def _finalize(
        self,
        df: pd.DataFrame,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str,
        invalid_value: Optional[float],
    ) -> str:
        tstart = hydromt_utils.parse_datetime(self.model.config["tstart"])
        tstop = hydromt_utils.parse_datetime(self.model.config["tstop"])

        if column_name not in df.columns:
            raise ValueError(f"No existe columna '{column_name}' en los datos de nivel del mar")

        df = df[[column_name]].copy()
        df.columns = ["1"]  # requerido por SFINCS
        df.index.name = "time"

        df = df.loc[tstart:tstop]
        df = df.dropna()

        if invalid_value is not None:
            df = df[df["1"] != invalid_value]

        if df.empty:
            raise RuntimeError("Serie de nivel del mar quedó vacía tras el filtrado")

        out_path = os.path.join(self.model.root, out_filename)
        df.to_csv(out_path)

        pnts = gpd.points_from_xy([x_bnd], [y_bnd])
        bnd = gpd.GeoDataFrame(index=[1], geometry=pnts, crs=self.model.crs)

        self.model.setup_waterlevel_forcing(timeseries=df, locations=bnd)

        return out_path

    def from_dataframe(
        self,
        df: pd.DataFrame,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
    ) -> str:
        """
        Genera el forzante de nivel del mar a partir de un DataFrame ya
        preparado (hora local, y ya con cualquier corrección de datum que
        haga falta aplicada por quien llama), y lo registra en el modelo.

        Este es el método a usar después de
        :meth:`get_waterlevel_from_UHSLC` - ahí es donde el script del
        caso aplica su propia corrección específica de estación (ver
        ``main_xbeach.py`` para el patrón exacto con la estación 737),
        exactamente igual que hace XBeach.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame con índice de tiempo en hora local y una columna con
            los valores de nivel del mar.
        column_name : str
            Nombre de la columna con los valores de nivel del mar.
        x_bnd, y_bnd : float
            Coordenadas del punto de frontera en el CRS del modelo.
        out_filename : str, optional
            Nombre del archivo de salida (por defecto ``"bzs.csv"``).
        invalid_value : float or None, optional
            Valor que representa datos inválidos en la serie. Si es
            ``None``, no se aplica filtrado.

        Returns
        -------
        str
            Ruta completa del archivo generado dentro del modelo.
        """
        return self._finalize(df, column_name, x_bnd, y_bnd, out_filename, invalid_value)

    def from_csv(
        self,
        csv_path: str,
        column_name: str,
        x_bnd: float,
        y_bnd: float,
        out_filename: str = "bzs.csv",
        invalid_value: Optional[float] = -32.767,
        shift_utc_to_local: bool = True,
    ) -> str:
        """
        Genera el forzante de nivel del mar a partir de un archivo CSV en
        disco (p. ej. una serie ya preparada que no proviene de UHSLC).

        A diferencia de :meth:`from_dataframe`, este método asume por
        defecto que el CSV está en UTC y lo desplaza a hora local de
        Colombia (UTC-5) - útil para archivos legados que no pasaron por
        :meth:`get_waterlevel_from_UHSLC` (que ya entrega hora local).

        Parameters
        ----------
        csv_path : str
            Ruta al archivo CSV con la serie temporal.
        column_name : str
            Nombre de la columna con los valores de nivel del mar.
        x_bnd, y_bnd : float
            Coordenadas del punto de frontera en el CRS del modelo.
        out_filename : str, optional
            Nombre del archivo de salida (por defecto ``"bzs.csv"``).
        invalid_value : float or None, optional
            Valor que representa datos inválidos en la serie.
        shift_utc_to_local : bool, optional
            Si es True (por defecto), resta 5 horas al índice para
            convertir de UTC a hora local. Poner en ``False`` si el CSV
            ya está en hora local.

        Returns
        -------
        str
            Ruta completa del archivo generado dentro del modelo.
        """
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

        if shift_utc_to_local:
            df.index = df.index - pd.Timedelta(hours=5)

        return self._finalize(df, column_name, x_bnd, y_bnd, out_filename, invalid_value)
