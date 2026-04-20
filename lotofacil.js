export default async function handler(request) {
  try {
    const response = await fetch(
      "https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil",
      {
        headers: {
          "User-Agent": "Mozilla/5.0",
          "Accept": "application/json",
        },
      }
    );

    const data = await response.json();

    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ erro: true, detalhe: e.toString() }),
      { status: 500 }
    );
  }
}
