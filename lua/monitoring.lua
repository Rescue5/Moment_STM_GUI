local tag = 'idle'
local lastTele = {}

-- Коэффициенты масштабирования для тензодатчиков
--local scaleFactors = {-220.4, -490510.5, -474912.8} -- По умолчанию установлены коэффициенты 1
local scaleFactors = {-430.468, -490510.5, -474912.8} -- По умолчанию установлены коэффициенты 1

local rpmcoef = 1
--local current_coef = 0,955882353

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

-- Проверка, находится ли значение в таблице
local function isInTable(value, tbl)
   if type(tbl) ~= "table" then
      error("Second argument must be a table")
   end
   for _, v in ipairs(tbl) do
      if v == value then
         return true
      end
   end
   return false
end

-- С температурой доделать
local function printTelemetry(t)
   local lopasti = intParam('lopasti', 3)
   local moment = (applyScale(t.Load2, 2) + applyScale(t.Load3, 3)) / 2
   local rpm = t.MotorRPM / lopasti
   local current = t.MotorI * 0.9514
   local power = current * t.MotorU
   local mech_power =  ((moment * rpm * 1000.0)/9549.0)
   local kpd = mech_power/power
   local str = string.format(
      'Скорость:%d:Момент:%.04f:Тяга:%d:Об/мин:%d:Ток:%.02f:Напряжение:%.02f:Мощность:%.02f:Температура:%.02f:Мех.Мощность:%.02f:КПД:%.02f',
      t.Throttle,
      moment, -- Средний момент
      applyScale(t.Load1, 1), -- Тяга
      rpm,
      current,
      t.MotorU,
      power,
      t.Temp1,
      mech_power,
      kpd
   )
   print(str)
end

local function onTelemetry(t)
   t.Tag = tag
   lastTele = t
   printTelemetry(t)
end

local function onDisconnect()
   print('Motor stopped')
end

--------------------------------------------------------------------------------

local function test(t)
   local lopasti = intParam('lopasti', 3)
   local delay    = intParam('delay', 250)
   local pulseMin = intParam('pulseMin', 1000)
   local pulseMax = intParam('pulseMax', 2000)
   local pulseInc = intParam('pulseInc',   25)

   sleep(1000)

   --
   -- фаза тестирования и снятия телеметрии с каждой 100
   --
   tag = 'acceleration'
   while true do
         sleep(delay)    -- Обычная задержка
      end
   end

--------------------------------------------------------------------------------

return {
   Test         = test,
   OnConnect    = onConnect,
   OnTelemetry  = onTelemetry,
   OnDisconnect = onDisconnect,
   SetScale     = setScale, -- Экспортируем функцию для установки коэффициентов
}