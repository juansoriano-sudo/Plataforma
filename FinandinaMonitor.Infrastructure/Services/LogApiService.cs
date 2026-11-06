using System;
using System.Threading.Tasks;
using Dapper;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using MySqlConnector;

namespace FinandinaMonitor.Infrastructure.Services
{
    public class LogApiService : ILogApiService
    {
        // Registro inicial del flujo de firma: se guarda con Metodo='SavePendingSignature' y
        // Descripcion='Guardado exitoso'. Se excluye a propósito la variante
        // "Ya existe un numero de radicado con este numero de producto y subproducto",
        // que corresponde a un intento fallido y no trae la información completa de la solicitud.
        private const string MetodoObjetivo = "SavePendingSignature";
        private const string DescripcionObjetivo = "Guardado exitoso";

        // Registro de reproceso de firma: se guarda con Metodo='SingDocuments' y
        // Descripcion='Inicia proceso de Firma'. Es un flujo independiente del anterior
        // (no debe mezclarse con el Adicional de SavePendingSignature/Guardado exitoso).
        private const string MetodoInicioFirma = "SingDocuments";
        private const string DescripcionInicioFirma = "Inicia proceso de Firma";

        private const int MesesHaciaAtras = 12;

        private readonly string _connectionString;
        private readonly ILogger<LogApiService> _logger;

        public LogApiService(IConfiguration configuration, ILogger<LogApiService> logger)
        {
            _connectionString = configuration.GetConnectionString("MariaDbLogs")
                ?? throw new ArgumentNullException(nameof(configuration), "La cadena de conexión 'MariaDbLogs' no se encuentra configurada.");
            _logger = logger;
        }

        public async Task<(bool IsConnected, string Message)> CheckHealthAsync()
        {
            try
            {
                await using var connection = new MySqlConnection(_connectionString);
                await connection.OpenAsync();
                return (true, "Conectado");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error al conectar con la base de datos MariaDB de logs (LogMotorFirma).");
                return (false, "No fue posible conectar a la base de datos MariaDB de logs.");
            }
        }

        public async Task<(bool Success, string? Adicional, string? ErrorMessage)> GetAdicionalAsync(long idSolicitud)
        {
            try
            {
                await using var connection = new MySqlConnection(_connectionString);
                await connection.OpenAsync();

                var adicional = await QueryAdicionalAsync(connection, "Log", idSolicitud);

                if (string.IsNullOrWhiteSpace(adicional))
                {
                    var mesReferencia = DateTime.Now;
                    for (var i = 0; i < MesesHaciaAtras && string.IsNullOrWhiteSpace(adicional); i++)
                    {
                        var tablaHistorica = "Log_" + mesReferencia.ToString("yyyyMM");
                        adicional = await QueryAdicionalAsync(connection, tablaHistorica, idSolicitud);
                        mesReferencia = mesReferencia.AddMonths(-1);
                    }
                }

                if (string.IsNullOrWhiteSpace(adicional))
                {
                    return (false, null, $"Sin resultados para Documento={idSolicitud}");
                }

                return (true, adicional, null);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Excepción al consultar MariaDB para {IdSolicitud}.", idSolicitud);
                return (false, null, "Excepción interna al consultar la base de datos");
            }
        }

        // Payload (Adicional) que se debe reenviar a /api/Management/SingDocuments para reprocesar
        // la firma: proviene del log de "Inicia proceso de Firma" (Metodo='SingDocuments'), un
        // flujo independiente del de GetAdicionalAsync (origen del producto / SavePendingSignature).
        public async Task<(bool Success, string? Adicional, string? ErrorMessage)> GetAdicionalInicioFirmaAsync(long idSolicitud)
        {
            try
            {
                await using var connection = new MySqlConnection(_connectionString);
                await connection.OpenAsync();

                var adicional = await QueryAdicionalAsync(connection, "Log", idSolicitud, MetodoInicioFirma, DescripcionInicioFirma);

                if (string.IsNullOrWhiteSpace(adicional))
                {
                    var mesReferencia = DateTime.Now;
                    for (var i = 0; i < MesesHaciaAtras && string.IsNullOrWhiteSpace(adicional); i++)
                    {
                        var tablaHistorica = "Log_" + mesReferencia.ToString("yyyyMM");
                        adicional = await QueryAdicionalAsync(connection, tablaHistorica, idSolicitud, MetodoInicioFirma, DescripcionInicioFirma);
                        mesReferencia = mesReferencia.AddMonths(-1);
                    }
                }

                if (string.IsNullOrWhiteSpace(adicional))
                {
                    return (false, null, $"Sin resultados de 'Inicia proceso de Firma' para Documento={idSolicitud}");
                }

                return (true, adicional, null);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Excepción al consultar el Adicional de inicio de firma en MariaDB para {IdSolicitud}.", idSolicitud);
                return (false, null, "Excepción interna al consultar la base de datos");
            }
        }

        // El nombre de tabla histórica (Log_yyyyMM) se genera internamente, nunca a partir
        // de entrada de usuario, por lo que interpolarlo en el SQL es seguro.
        private static async Task<string?> QueryAdicionalAsync(MySqlConnection connection, string table, long idSolicitud)
            => await QueryAdicionalAsync(connection, table, idSolicitud, MetodoObjetivo, DescripcionObjetivo);

        private static async Task<string?> QueryAdicionalAsync(MySqlConnection connection, string table, long idSolicitud, string metodo, string descripcionLike)
        {
            var sql = $@"SELECT Adicional
                         FROM `{table}`
                         WHERE Documento = @Documento
                           AND Metodo = @Metodo
                           AND Descripcion LIKE @Descripcion
                         ORDER BY Fecha DESC
                         LIMIT 1";

            try
            {
                return await connection.QueryFirstOrDefaultAsync<string?>(sql, new
                {
                    Documento = idSolicitud.ToString(),
                    Metodo = metodo,
                    Descripcion = $"%{descripcionLike}%"
                });
            }
            catch (MySqlException ex) when (ex.ErrorCode == MySqlErrorCode.NoSuchTable)
            {
                return null;
            }
        }

    }
}
