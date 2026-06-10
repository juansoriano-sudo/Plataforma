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
    t2.MontoAprobado
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
    }
}
