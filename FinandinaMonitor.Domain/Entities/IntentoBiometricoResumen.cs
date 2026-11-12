using System;
using System.Collections.Generic;

namespace FinandinaMonitor.Domain.Entities
{
    public class IntentoBiometricoResumen
    {
        public int TotalIntentos { get; set; }
        public int IntentosRegla0 { get; set; }
        public int IntentosRegla1 { get; set; }
        public int IntentosRegla99 { get; set; }
        public int IntentosCanal0 { get; set; }
        public int IntentosCanal1 { get; set; }

        public long? UltimoIdCaso { get; set; }
        public int? UltimoIdRegla { get; set; }
        public int? UltimoIdEstado { get; set; }
        public string? UltimoEstado { get; set; }
        public DateTime? UltimaFechaCreo { get; set; }

        public List<IntentoBiometricoDetalle> Intentos { get; set; } = new();
    }
}
