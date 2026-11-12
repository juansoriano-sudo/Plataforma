using System;

namespace FinandinaMonitor.Domain.Entities
{
    public class Usuario
    {
        public int Id { get; set; }
        public string Username { get; set; } = string.Empty;
        public string PasswordHash { get; set; } = string.Empty;
        public bool EsAdmin { get; set; }
        public bool PuedeBorrar { get; set; }
        public bool PuedeReprocesar { get; set; }
        public bool PuedeVerCompleto { get; set; }
        public bool Activo { get; set; } = true;
        public DateTime FechaCreacion { get; set; }
    }
}
