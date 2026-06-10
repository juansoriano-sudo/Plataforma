namespace FinandinaMonitor.Domain.DTOs
{
    /// <summary>
    /// DTO genérico para la solicitud de reproceso de documentos de firma.
    /// Esta estructura se actualizará con el JSON real requerido por la API.
    /// </summary>
    public class ReprocesoRequestDto
    {
        public long IdSolicitud { get; set; }
        public string? RadNumber { get; set; }
        public string? NumeroDocumento { get; set; }
        // Se pueden añadir más campos según el contrato final de la API
    }
}
