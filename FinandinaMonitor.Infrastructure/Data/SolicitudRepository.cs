using System.Collections.Generic;
using System.Data;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;
using Dapper;
using FinandinaMonitor.Domain.Entities;
using FinandinaMonitor.Domain.Interfaces;

namespace FinandinaMonitor.Infrastructure.Data
{
    public class SolicitudRepository : ISolicitudRepository
    {
        private readonly string _connectionString;

        public SolicitudRepository(IConfiguration configuration)
        {
            _connectionString = configuration.GetConnectionString("FinandinaDb")
                                ?? throw new System.ArgumentNullException(nameof(configuration), "La cadena de conexión 'FinandinaDb' no se encuentra configurada.");
        }

        public async Task<IEnumerable<SolicitudFirma>> GetPendientesProcesarAsync(int estadoFirma = 100, int estadoBiometria = 70)
        {
            bool filtrarPorFecha = estadoFirma == 1000 && estadoBiometria == 70;

            string sql = @"
SELECT
    t2.IdSolicitud,
    t2.IdEstadoFirma,
    t2.IdEstadoBiometria,
    t1.Observacion,
    t1.Descripcion,
    t2.RadNumber,
    t2.FechaCreacion,
    t2.FechaModificacion,
    t2.NumeroDocumento,
    t2.TipoDocumento,
    t2.MontoAprobado,
    t2.Origen,
    t2.EsVentaCruzada
FROM [MotorFirma].PendienteFirma.Estados AS t1
INNER JOIN [MotorFirma].PendienteFirma.Solicitudes AS t2
    ON t1.IdEstado = t2.IdEstadoBiometria
WHERE t2.IdEstadoBiometria = @EstadoBiometria
  AND t2.IdEstadoFirma = @EstadoFirma"
          + (filtrarPorFecha ? @"
  AND CAST(t2.FechaModificacion AS DATE) BETWEEN @FechaInicio AND @FechaFin" : "") + @"
ORDER BY t2.FechaModificacion DESC";

            var hoy = DateTime.Today;

            using IDbConnection db = new SqlConnection(_connectionString);
            return await db.QueryAsync<SolicitudFirma>(sql, new
            {
                EstadoFirma = estadoFirma,
                EstadoBiometria = estadoBiometria,
                FechaInicio = hoy,
                FechaFin = hoy
            });
        }

        public async Task<IEnumerable<SolicitudFirma>> GetPendientesPorEstadoBiometriaAsync(int estadoBiometria = 2000)
        {
            const string sql = @"
SELECT
    t2.IdSolicitud,
    t2.IdEstadoFirma,
    t2.IdEstadoBiometria,
    t1.Observacion,
    t1.Descripcion,
    t2.RadNumber,
    t2.FechaCreacion,
    t2.FechaModificacion,
    t2.NumeroDocumento,
    t2.TipoDocumento,
    t2.MontoAprobado,
    t2.Origen,
    t2.EsVentaCruzada
FROM [MotorFirma].PendienteFirma.Estados AS t1
INNER JOIN [MotorFirma].PendienteFirma.Solicitudes AS t2
    ON t1.IdEstado = t2.IdEstadoBiometria
WHERE t2.IdEstadoBiometria = @EstadoBiometria
ORDER BY t2.FechaModificacion DESC";

            using IDbConnection db = new SqlConnection(_connectionString);
            return await db.QueryAsync<SolicitudFirma>(sql, new { EstadoBiometria = estadoBiometria });
        }

        public async Task<IEnumerable<SolicitudFirma>> BuscarSolicitudesAsync(string? termino, int? estadoFirma = null, int? estadoBiometria = null)
        {
            var terminoLimpio = termino?.Trim();
            long? idSolicitud = !string.IsNullOrEmpty(terminoLimpio) && long.TryParse(terminoLimpio, out var id) ? id : (long?)null;

            var (whereClause, parametros) = ConstruirFiltro(terminoLimpio, idSolicitud, estadoFirma, estadoBiometria);

            string sql = @"
SELECT TOP 50
    t2.IdSolicitud,
    t2.IdEstadoFirma,
    t2.IdEstadoBiometria,
    t1.Observacion,
    t1.Descripcion,
    t2.RadNumber,
    t2.FechaCreacion,
    t2.FechaModificacion,
    t2.NumeroDocumento,
    t2.TipoDocumento,
    t2.MontoAprobado,
    t2.Origen,
    t2.EsVentaCruzada
FROM [MotorFirma].PendienteFirma.Estados AS t1
INNER JOIN [MotorFirma].PendienteFirma.Solicitudes AS t2
    ON t1.IdEstado = t2.IdEstadoBiometria
WHERE " + whereClause + @"
ORDER BY t2.FechaModificacion DESC";

            using IDbConnection db = new SqlConnection(_connectionString);
            return await db.QueryAsync<SolicitudFirma>(sql, parametros);
        }

        public async Task<int> ContarPorFiltroAsync(string? termino, int? estadoFirma, int? estadoBiometria)
        {
            var terminoLimpio = termino?.Trim();
            long? idSolicitud = !string.IsNullOrEmpty(terminoLimpio) && long.TryParse(terminoLimpio, out var id) ? id : (long?)null;

            var (whereClause, parametros) = ConstruirFiltro(terminoLimpio, idSolicitud, estadoFirma, estadoBiometria);

            string sql = @"
SELECT COUNT(*)
FROM [MotorFirma].PendienteFirma.Estados AS t1
INNER JOIN [MotorFirma].PendienteFirma.Solicitudes AS t2
    ON t1.IdEstado = t2.IdEstadoBiometria
WHERE " + whereClause;

            using IDbConnection db = new SqlConnection(_connectionString);
            return await db.ExecuteScalarAsync<int>(sql, parametros);
        }

        /// <summary>
        /// Construye el WHERE y los parámetros compartidos entre la búsqueda y el conteo por filtro.
        /// Al menos uno de los criterios (término, estado de firma o estado de biometría) debe estar presente.
        /// </summary>
        private static (string WhereClause, object Parametros) ConstruirFiltro(
            string? terminoLimpio, long? idSolicitud, int? estadoFirma, int? estadoBiometria)
        {
            var condiciones = new List<string>();

            if (!string.IsNullOrEmpty(terminoLimpio))
            {
                condiciones.Add("((@IdSolicitud IS NOT NULL AND t2.IdSolicitud = @IdSolicitud) OR t2.RadNumber LIKE @Termino OR t2.NumeroDocumento LIKE @Termino)");
            }

            if (estadoFirma.HasValue)
            {
                condiciones.Add("t2.IdEstadoFirma = @EstadoFirma");
            }

            if (estadoBiometria.HasValue)
            {
                condiciones.Add("t2.IdEstadoBiometria = @EstadoBiometria");
            }

            var whereClause = condiciones.Count > 0
                ? string.Join(" AND ", condiciones)
                : "1 = 0";

            var parametros = new
            {
                IdSolicitud = idSolicitud,
                Termino = $"%{terminoLimpio}%",
                EstadoFirma = estadoFirma,
                EstadoBiometria = estadoBiometria
            };

            return (whereClause, parametros);
        }

        public async Task<int> GetCountExitosasHoyAsync(System.DateTime fechaInicio, System.DateTime fechaFin, int estadoFirma = 1000, int estadoBiometria = 70)
        {
            string sql = @"
    SELECT COUNT(*) 
    FROM [MotorFirma].PendienteFirma.Solicitudes AS t2
    WHERE t2.IdEstadoBiometria = @EstadoBiometria
      AND t2.IdEstadoFirma = @EstadoFirma
      AND CAST(t2.FechaModificacion AS DATE) BETWEEN @FechaInicio AND @FechaFin";

            using IDbConnection db = new SqlConnection(_connectionString);
            return await db.ExecuteScalarAsync<int>(sql, new
            {
                EstadoFirma = estadoFirma,
                EstadoBiometria = estadoBiometria,
                FechaInicio = fechaInicio,
                FechaFin = fechaFin
            });
        }

        public async Task<(int IdEstadoFirma, int IdEstadoBiometria)?> GetEstadoActualAsync(long idSolicitud)
        {
            const string sql = @"
    SELECT IdEstadoFirma AS IdEstadoFirma, IdEstadoBiometria AS IdEstadoBiometria
    FROM [MotorFirma].PendienteFirma.Solicitudes
    WHERE IdSolicitud = @IdSolicitud";

            using IDbConnection db = new SqlConnection(_connectionString);
            var row = await db.QueryFirstOrDefaultAsync<EstadoSolicitudRow>(sql, new { IdSolicitud = idSolicitud });
            return row is null ? null : (row.IdEstadoFirma, row.IdEstadoBiometria);
        }

        private class EstadoSolicitudRow
        {
            public int IdEstadoFirma { get; set; }
            public int IdEstadoBiometria { get; set; }
        }
    }
}
