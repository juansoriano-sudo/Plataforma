using System;

namespace FinandinaMonitor.Domain.Entities
{
    public class IntentoBiometricoDetalle
    {
        public long IdCaso { get; set; }
        public long? IdCliente { get; set; }
        public int? IdCanal { get; set; }
        public int? IdRegla { get; set; }
        public int? IdEstado { get; set; }
        public string? Estado { get; set; }
        public DateTime? FechaCreo { get; set; }
    }
}
