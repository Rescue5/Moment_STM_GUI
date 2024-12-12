local tag = 'idle'
local lastTele = {}

-- Коэффициенты масштабирования для тензодатчиков
-- local scaleFactors = {-220.4, -490510.5, -474912.8} -- По умолчанию установлены коэффициенты 1
local scaleFactors = {-430.468, -868021, -474912.8} -- По умолчанию установлены коэффициенты 1
local rpmcoef = 1

local function setScale(index, scale)
   if index < 1 or index > 3 then
      error("Index out of range. Valid indexes are 1, 2, 3.")
   end
   scaleFactors[index] = scale
   print(string.format("Scale factor for Load%d set to %.2f", index, scale))
end

local function applyScale(value, index)
   return value / scaleFactors[index] -- Преобразование сырых данных в реальные
end

local function onConnect()
   local sampleRate = intParam('sampleRate', 10)
   sample(sampleRate)
   tare()
end

-- С температурой доделать
local function printTelemetry(t)
   local str = string.format(
      'Скорость:%d:Момент:%.05f:Тяга:%.02f:Об/мин:%d:Ток:%.02f:Напряжение:%.02f:Мощность:%.02f:Температура:%.02f',
      t.Throttle,
      applyScale(t.Load2, 2), -- момент
      applyScale(t.Load1, 1), -- Тяга
      t.MotorRPM / 3,
      t.MotorI,
      t.MotorU,
      t.MotorP,
      t.Temp1

   )
   print(str)
end

local function onConnect()
   local sampleRate = intParam('sampleRate', 10)
   sample(sampleRate)
   tare()
end


local function onTelemetry(t)
   t.Tag = tag
   lastTele = t
   if t.Throttle % 100 == 0 then
      printTelemetry(t)
   end
end

local function onDisconnect()
   print('Motor stopped')
end

--------------------------------------------------------------------------------

local function coolingMode()
   local delay = 100 -- Задержка между шагами разгона
   local targetThrottle = 800 -- Целевое значение газа

   tag = 'cooling'

   -- Включаем вентиляторы на 100%
   chiller(1, 100)

   -- Плавный разгон до 1200
   for i = 800, targetThrottle, 10 do
      throttle(i)
      sleep(delay)
   end

   -- Удерживаем скорость 1200 бесконечно
   throttle(targetThrottle)
   while true do
      sleep(1000) -- Ждём, пока не прервут выполнение
   end
end

--------------------------------------------------------------------------------

local function test()
   -- Вызов режима охлаждения
   coolingMode()
end

--------------------------------------------------------------------------------

return {
   Test         = test,
   OnConnect    = onConnect,
   OnTelemetry  = onTelemetry,
   OnDisconnect = onDisconnect,
}