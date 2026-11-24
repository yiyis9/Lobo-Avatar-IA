<?php

namespace App\Services;

use App\Exceptions\FastApiUnavailable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

class FastApiClient
{
    public function request(string $method, string $path, array $payload = [], ?string $token = null): Response
    {
        $request = $this->requestBuilder();
        if ($token !== null && $token !== '') {
            $request = $request->withToken($token);
        }

        try {
            return $request->send(strtoupper($method), ltrim($path, '/'), $payload === [] ? [] : ['json' => $payload]);
        } catch (ConnectionException $exception) {
            throw new FastApiUnavailable('FastAPI no está disponible en este momento.', previous: $exception);
        }
    }

    private function requestBuilder(): PendingRequest
    {
        return Http::baseUrl(rtrim((string) config('services.fastapi.base_url'), '/'))
            ->acceptJson()
            ->asJson()
            ->connectTimeout(2)
            ->timeout((int) config('services.fastapi.timeout', 8));
    }
}
