-- Datos sinteticos para el ejemplo. Nada de esto es real.

INSERT INTO `clientes` (`nombre`, `email`, `password`, `id_localidad`, `alta`) VALUES
  ('Ana Gomez', 'ana@example.com', 'e10adc3949ba59abbe56e057f20f883e', 'L01', '2021-03-04'),
  ('Beto Diaz', 'beto@example.com', '25d55ad283aa400af464c76d713c07ad', 'L02', '2020-11-19'),
  ('Carla Ruiz', 'carla@example.com', '5f4dcc3b5aa765d61d8327deb882cf99', 'L01', '2022-06-30');

INSERT INTO `categorias` (`nombre`) VALUES ('Herramientas'), ('Insumos'), ('Repuestos');

INSERT INTO `productos` (`nombre`, `precio`, `id_categoria`, `activo`, `fecha_alta`) VALUES
  ('Taladro 500W', 45900.00, 1, 'S', '2022-01-15'),
  ('Cinta aisladora', 1200.50, 2, 'S', '2022-02-01'),
  ('Motor de porton', 128000.00, 3, 'N', '2021-09-10');

INSERT INTO `pedidos` (`id_cliente`, `fecha`, `total`, `estado`, `observaciones`) VALUES
  (1, '2024-05-02', '47100.50', 'ENTREGADO', ''),
  (2, '2024-05-03', '128000.00', 'PENDIENTE', 'pasa despues de las 18'),
  (3, '2024-05-07', '1200.50', 'ENTREGADO', NULL);

INSERT INTO `pedido_items` (`id_pedido`, `id_producto`, `cantidad`, `precio`) VALUES
  (1, 1, 1, 45900.00),
  (1, 2, 1, 1200.50),
  (2, 3, 1, 128000.00),
  (3, 2, 1, 1200.50);

INSERT INTO `pagos` (`id_pedido`, `id_metodo`, `importe`, `fecha_pago`, `id_factura`) VALUES
  (1, 'EF', 47100.50, '2024-05-02', 1001),
  (2, 'TR', 64000.00, '2024-05-03', 1002),
  (3, 'TC', 1200.50, '2024-05-07', NULL);

INSERT INTO `usuarios` (`usuario`, `clave`, `id_rol`, `ultimo_acceso`) VALUES
  ('admin', '21232f297a57a5a743894a0e4a801fc3', '1', '2024-05-07 18:22:11'),
  ('vendedor', 'e10adc3949ba59abbe56e057f20f883e', '2', '2024-05-06 09:01:44');

INSERT INTO `log_accesos` (`id_usuario`, `ip`, `cuando`, `accion`) VALUES
  ('1', '10.0.0.5', '2024-05-07 18:22:11', 'login ok'),
  ('2', '10.0.0.9', '2024-05-06 09:01:44', 'login ok');

INSERT INTO `proveedores` (`razon_social`, `cuit`) VALUES ('Insumos del Sur SRL', '30-71234567-8');

INSERT INTO `config` (`clave`, `valor`) VALUES ('iva', '21'), ('moneda', 'ARS');

INSERT INTO `reportes_mensuales` (`anio`, `total.'MES 1'`, `total.'MES 2'`, `Order`) VALUES
  ('2024', 120000.00, 98000.00, 'A');

INSERT INTO `envios` (`id_pedido`, `direccion`, `fecha_envio`, `id_transporte`) VALUES
  (1, 'Av. Siempre Viva 742', '2024-05-04', 'TR1');
