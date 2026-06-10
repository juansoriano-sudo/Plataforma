using System.Threading.Tasks;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface ILogApiService
    {
        Task<(bool IsConnected, string Message)> CheckHealthAsync();
        Task<(bool Success, string? Adicional, string? ErrorMessage)> GetAdicionalAsync(long idSolicitud);
    }
}
