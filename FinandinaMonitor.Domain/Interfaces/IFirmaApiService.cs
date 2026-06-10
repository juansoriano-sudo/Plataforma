using System.Collections.Generic;
using System.Threading.Tasks;
using FinandinaMonitor.Domain.DTOs;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IFirmaApiService
    {
        Task<bool> ReprocesarSolicitudAsync(string adicionalJson);
    }
}
