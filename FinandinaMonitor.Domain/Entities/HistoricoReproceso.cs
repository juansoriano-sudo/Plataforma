using System;
using FinandinaMonitor.Domain.Helpers;

namespace FinandinaMonitor.Domain.Entities
{
    public class HistoricoReproceso
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public long IdSolicitud { get; set; }
        public string? RadNumber { get; set; }
        public string? NumeroDocumento { get; set; }
        public string TipoReproceso { get; set; } = string.Empty;
        public string? Usuario { get; set; }
        public int EstadoFirmaInicial { get; set; }
        public int EstadoBiometriaInicial { get; set; }
        public DateTime FechaReproceso { get; set; } = HoraLocal.Ahora;

        public bool Verificado { get; set; }
        public bool? Avanzo { get; set; }
        public int? EstadoFirmaVerificado { get; set; }
        public int? EstadoBiometriaVerificado { get; set; }
        public DateTime? FechaVerificacion { get; set; }
    }
}
