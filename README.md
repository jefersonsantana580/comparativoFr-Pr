# 📊 Comparativo de Demanda (Streamlit)

App em **Streamlit** para comparação de cenários de demanda entre diferentes versões de planejamento, permitindo alternar dinamicamente a visão entre:

- **F.Response − Request**
- **Request − Plan**

O app mantém **a mesma lógica de cálculo, filtros e cenários**, alterando apenas a base de comparação conforme a visão selecionada.

---

## 🚀 Funcionalidades

- Upload de arquivo Excel pelo usuário
- Detecção automática das colunas de mês (`jan/26`, `fev/26`, etc.)
- Toggle de visão:
  - **F.Response − Request**
  - **Request − Plan**
- Cálculo mensal e total por linha
- Destaque visual de valores positivos e negativos
- Download do Excel resultante

---

## 📘 Estrutura esperada do Excel

O arquivo Excel deve conter obrigatoriamente as abas:

- `PLAN`
- `REQUEST`
- `F.RESPONSE`

Cada aba deve conter colunas dimensionais (ex.: PRODUCT, SERIES, MARKET etc.) e colunas mensais no padrão `jan/26`, `fev/26`, ...

---

## 🧮 Lógica de cálculo

| Visão selecionada | Cálculo |
|------------------|---------|
| F.Response − Request | F.RESPONSE − REQUEST |
| Request − Plan | REQUEST − PLAN |

---

## ▶️ Execução local

```bash
pip install -r requirements.txt
streamlit run comparativo_app.py
```

---

## ✅ Observações

- O app não utiliza arquivos locais fixos
- Todo processamento acontece a partir do Excel enviado pelo usuário
- Compatível com Streamlit Cloud e Azure
