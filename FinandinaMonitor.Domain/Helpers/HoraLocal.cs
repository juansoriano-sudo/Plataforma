using System;

namespace FinandinaMonitor.Domain.Helpers
{
    /// <summary>
    /// Punto único para obtener la hora local de Colombia (UTC-05:00, sin horario de verano),
    /// independientemente de cómo esté configurada la zona horaria del sistema operativo
    /// donde corra el servidor. Evita que las fechas mostradas en el dashboard (creación,
    /// expiración de alertas, histórico, etc.) se desfasen respecto a la hora real de Bogotá.
    /// </summary>
    public static class HoraLocal
    {
        private static readonly TimeZoneInfo ZonaColombia = ResolverZonaColombia();

        public static DateTime Ahora => TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, ZonaColombia);

        private static TimeZoneInfo ResolverZonaColombia()
        {
            try
            {
                // Id de Windows
                return TimeZoneInfo.FindSystemTimeZoneById("SA Pacific Standard Time");
            }
            catch (TimeZoneNotFoundException)
            {
                try
                {
                    // Id IANA (Linux/macOS)
                    return TimeZoneInfo.FindSystemTimeZoneById("America/Bogota");
                }
                catch (TimeZoneNotFoundException)
                {
                    // Último recurso: desplazamiento fijo UTC-5.
                    return TimeZoneInfo.CreateCustomTimeZone("UTC-05:00", TimeSpan.FromHours(-5), "Colombia (UTC-5)", "Colombia (UTC-5)");
                }
            }
        }
    }
}
