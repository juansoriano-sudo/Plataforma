using System.Threading.Tasks;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IReprocesoAvanzadoApiService
    {
        Task<(bool Success, string? ErrorMessage)> ReprocessCasesAsync(string radNumber, bool isCrossSelling);

        Task<(bool Success, string? ErrorMessage)> SaveSignatureAsync(string adicionalJson);

        Task<(bool Success, string? ErrorMessage)> UpdateStateAsync(long signProcessId, string signCodeState, string bioCodeState);
    }
}
