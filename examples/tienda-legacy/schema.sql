-- Esquema de ejemplo de legacy-lens.
-- Es un sistema INVENTADO, con los vicios tipicos de un legacy real:
-- sin foreign keys, sin PK en varias tablas, MyISAM, latin1, fechas en texto,
-- IDs en varchar, nombres hostiles y tablas gemelas.
-- Ningun dato ni nombre proviene de un sistema real.

DROP TABLE IF EXISTS `pedido_items`;
DROP TABLE IF EXISTS `pedidos`;
DROP TABLE IF EXISTS `pagos`;
DROP TABLE IF EXISTS `productos`;
DROP TABLE IF EXISTS `categorias`;
DROP TABLE IF EXISTS `clientes`;
DROP TABLE IF EXISTS `usuarios`;
DROP TABLE IF EXISTS `log_accesos`;
DROP TABLE IF EXISTS `proveedor`;
DROP TABLE IF EXISTS `proveedores`;
DROP TABLE IF EXISTS `config`;
DROP TABLE IF EXISTS `reportes_mensuales`;
DROP TABLE IF EXISTS `envios`;

CREATE TABLE `clientes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(120) DEFAULT NULL,
  `email` varchar(120) DEFAULT NULL,
  `password` varchar(32) DEFAULT NULL,
  `id_localidad` varchar(10) DEFAULT NULL,
  `alta` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `categorias` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(80) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `productos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(160) DEFAULT NULL,
  `precio` decimal(10,2) DEFAULT NULL,
  `id_categoria` int(11) DEFAULT NULL,
  `activo` enum('S','N') DEFAULT 'S',
  `fecha_alta` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_categoria` (`id_categoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `pedidos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `id_cliente` int(11) DEFAULT NULL,
  `fecha` varchar(10) DEFAULT NULL,
  `total` varchar(20) DEFAULT NULL,
  `estado` varchar(20) DEFAULT NULL,
  `observaciones` text,
  PRIMARY KEY (`id`),
  KEY `idx_cliente` (`id_cliente`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `pedido_items` (
  `id_pedido` int(11) DEFAULT NULL,
  `id_producto` int(11) DEFAULT NULL,
  `cantidad` int(11) DEFAULT NULL,
  `precio` decimal(10,2) DEFAULT NULL,
  KEY `idx_pedido` (`id_pedido`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `pagos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `id_pedido` int(11) DEFAULT NULL,
  `id_metodo` varchar(6) DEFAULT NULL,
  `importe` decimal(10,2) DEFAULT NULL,
  `fecha_pago` varchar(10) DEFAULT NULL,
  `id_factura` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario` varchar(40) DEFAULT NULL,
  `clave` varchar(32) DEFAULT NULL,
  `id_rol` varchar(4) DEFAULT NULL,
  `ultimo_acceso` varchar(19) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `log_accesos` (
  `id_usuario` varchar(20) DEFAULT NULL,
  `ip` varchar(45) DEFAULT NULL,
  `cuando` varchar(19) DEFAULT NULL,
  `accion` varchar(60) DEFAULT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `proveedores` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `razon_social` varchar(160) DEFAULT NULL,
  `cuit` varchar(13) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `proveedor` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(160) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `config` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `clave` varchar(60) DEFAULT NULL,
  `valor` text,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `reportes_mensuales` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `anio` varchar(4) DEFAULT NULL,
  `total.'MES 1'` decimal(12,2) DEFAULT NULL,
  `total.'MES 2'` decimal(12,2) DEFAULT NULL,
  `Order` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;

CREATE TABLE `envios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `id_pedido` int(11) DEFAULT NULL,
  `direccion` varchar(200) DEFAULT NULL,
  `fecha_envio` varchar(10) DEFAULT NULL,
  `id_transporte` varchar(8) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
