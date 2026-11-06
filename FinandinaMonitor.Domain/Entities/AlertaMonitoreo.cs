using System;
using FinandinaMonitor.Domain.Helpers;

namespace FinandinaMonitor.Domain.Entities
{
    /// <summary>
    /// Alerta de monitoreo temporal creada manualmente por el usuario desde el Buscador,
    /// para vigilar cuántas solicitudes cumplen un filtro (Estado Firma / Estado Biometría / término)
    /// durante una ventana de tiempo limitada.
    /// </summary>
    public class AlertaMonitoreo
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public string Descripcion { get; set; } = string.Empty;

        public int? EstadoFirma { get; set; }
        public int? EstadoBiometria { get; set; }
        public string? Termino { get; set; }

        public int Umbral { get; set; }
        public int DuracionMinutos { get; set; }

        public DateTime FechaCreacion { get; set; } = HoraLocal.Ahora;
        public DateTime FechaExpiracion { get; set; }

        public bool Activa { get; set; } = true;
        public int UltimoConteo { get; set; }
        public DateTime? UltimaEvaluacion { get; set; }

        public bool Disparada { get; set; }
        public DateTime? FechaDisparo { get; set; }
    }
}
