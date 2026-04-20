export default async function handler(req, res) {
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

    res.status(200).json(data);
  } catch (e) {
    res.status(500).json({ erro: true });
  }
}
