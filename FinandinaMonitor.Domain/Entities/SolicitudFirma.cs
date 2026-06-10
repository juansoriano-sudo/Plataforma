using System;

namespace FinandinaMonitor.Domain.Entities
{
    public class SolicitudFirma
    {
        public long IdSolicitud { get; set; }
        public int IdEstadoFirma { get; set; }
        public int IdEstadoBiometria { get; set; }
        public string? Observacion { get; set; }
        public string? Descripcion { get; set; }
        public string? RadNumber { get; set; }
        public DateTime FechaCreacion { get; set; }
        public DateTime FechaModificacion { get; set; }
        public string? NumeroDocumento { get; set; }
        public string? TipoDocumento { get; set; }
        public decimal MontoAprobado { get; set; }
    }
}
