using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.DTOs;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IFirmaApiService
    {
        Task<(bool Success, string? ErrorMessage)> ReprocesarSolicitudAsync(string adicionalJson, long? idSolicitud = null);
    }
}
