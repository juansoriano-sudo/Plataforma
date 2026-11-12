using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.Helpers;
using FinandinaMonitor.Domain.Interfaces;
using Microsoft.Extensions.Configuration;

namespace FinandinaMonitor.Infrastructure.Services
{
    /// <summary>
    /// Registra toda la actividad del monitor (login/logout, reprocesos, cambios de usuarios/permisos, etc.)
    /// en un archivo de texto por día, dentro de la carpeta configurada en "ActividadLog:Path"
    /// (por defecto "logs/actividad" relativo al directorio de la app).
    /// </summary>
    public class ActividadLogger : IActividadLogger
    {
        private readonly string _carpeta;
        private readonly SemaphoreSlim _lockEscritura = new(1, 1);

        public ActividadLogger(IConfiguration configuration)
        {
            _carpeta = configuration["ActividadLog:Path"] ?? Path.Combine("logs", "actividad");
            Directory.CreateDirectory(_carpeta);
        }

        public async Task RegistrarAsync(string? usuario, string accion, string detalle)
        {
            var ahora = HoraLocal.Ahora;
            var archivo = Path.Combine(_carpeta, $"{ahora:yyyy-MM-dd}.log");
            var linea = $"[{ahora:HH:mm:ss}] Usuario={usuario ?? "Anonimo"} | Accion={accion} | {detalle}{Environment.NewLine}";

            await _lockEscritura.WaitAsync();
            try
            {
                await File.AppendAllTextAsync(archivo, linea);
            }
            finally
            {
                _lockEscritura.Release();
            }
        }
    }
}
