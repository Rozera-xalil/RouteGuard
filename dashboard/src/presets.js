const pad = (n) => String(n).padStart(2, '0')

export function localDateTime(d = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function localDate(daysAhead) {
  const d = new Date()
  d.setDate(d.getDate() + daysAhead)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function blankOrder() {
  return {
    seller_id: '',
    seller_state: 'SP',
    seller_zip_code_prefix: 14409,
    customer_state: 'RJ',
    customer_zip_code_prefix: 27277,
    purchase: localDateTime(),
    promised: localDate(14),
    total_items: 2,
    total_item_price: 150,
    total_freight: 25.5,
    avg_product_weight_g: 800,
    avg_volume_cm3: 6000,
    payment_type: 'credit_card',
    max_installments: 3,
  }
}

export const presets = [
  { id: 'rio', patch: {} },
  {
    id: 'manaus',
    patch: {
      customer_state: 'AM',
      customer_zip_code_prefix: 69005,
      total_items: 1,
      total_item_price: 220,
      total_freight: 78.9,
      avg_product_weight_g: 2400,
      avg_volume_cm3: 18000,
      max_installments: 6,
      promised: localDate(9),
    },
  },
  {
    id: 'local',
    patch: {
      seller_zip_code_prefix: 1310,
      customer_state: 'SP',
      customer_zip_code_prefix: 4538,
      total_items: 1,
      total_item_price: 59.9,
      total_freight: 12.4,
      avg_product_weight_g: 350,
      avg_volume_cm3: 2400,
      max_installments: 1,
      payment_type: 'boleto',
      promised: localDate(8),
    },
  },
]

export function toPayload(f) {
  const items = Number(f.total_items)
  const price = Number(f.total_item_price)
  const freight = Number(f.total_freight)
  const num = (v) => (v === '' || v === null ? null : Number(v))
  return {
    seller_id: f.seller_id.trim() || null,
    order_purchase_timestamp: `${f.purchase}:00`,
    order_estimated_delivery_date: `${f.promised}T00:00:00`,
    customer_state: f.customer_state,
    seller_state: f.seller_state,
    customer_zip_code_prefix: Number(f.customer_zip_code_prefix),
    seller_zip_code_prefix: Number(f.seller_zip_code_prefix),
    total_items: items,
    total_item_price: price,
    total_freight: freight,
    avg_item_price: items > 0 ? price / items : price,
    avg_product_weight_g: num(f.avg_product_weight_g),
    avg_volume_cm3: num(f.avg_volume_cm3),
    max_installments: Number(f.max_installments),
    total_payment_value: price + freight,
    payment_types_used: f.payment_type,
  }
}

export const STATES = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
]
