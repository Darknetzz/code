<?php

class Rand {

    /* -------------------------------------------------------------------------- */
    /*                                 Initialize                                 */
    /* -------------------------------------------------------------------------- */
    public function __construct()
    {
        $this->str_lowercase = range("a", "z");
        $this->str_uppercase = range("A", "Z");
        $this->str_digits    = range("0", "9");
        $this->str_symbols   = str_split("!.:,;-");
        $this->str_all       = array_merge($this->str_lowercase,$this->str_uppercase,$this->str_digits,$this->str_symbols);
    }

    /* -------------------------------------------------------------------------- */
    /*                  Check if (any) of array values in string                  */
    /* -------------------------------------------------------------------------- */
    public function arrayInString($array, $string) {
        foreach ($array as $char) {
            if (strpos($char, $string) !== FALSE) {
                return true;
            }
        }
        return false;
    }

    /* -------------------------------------------------------------------------- */
    /*                               Generate string                              */
    /* -------------------------------------------------------------------------- */
    public function genStr($len = 24, $charset = null, $required = []) {
        $this->returnValue = "";

        if ($charset == null) {
            $charset = $this->str_all;
        }

        if (is_array($charset)) {
            $count = count($charset);
        } elseif (is_string($charset)) {
            $count = strlen($charset);
        } else {
            die("charset for genStr wasn't an array or string.");
        }

        for ($i=0; $i <= $len-1; $i++) {
            $roll = mt_rand(0,$count-1);
            $this->returnValue .= $charset[$roll];
        }

        if (in_array("lower", $required) && !$this->arrayInString($this->str_lowercase, $this->returnValue)) {
            $this->returnValue .= $this->str_lowercase[mt_rand(0,count($this->str_lowercase-1))];
        }
        if (in_array("upper", $required) && !$this->arrayInString($this->str_uppercase, $this->returnValue)) {
            $this->returnValue .= $this->str_uppercase[mt_rand(0,count($this->str_uppercase-1))];
        }
        if (in_array("digit", $required) && !$this->arrayInString($this->str_digits, $this->returnValue)) {
            $this->returnValue .= $this->str_digits[mt_rand(0,count($this->str_digits-1))];
        }
        if (in_array("symbol", $required) && !$this->arrayInString($this->str_symbols, $this->returnValue)) {
            $this->returnValue .= $this->str_symbols[mt_rand(0,count($this->str_symbols-1))];
        }

        $this->returnValue = str_shuffle($this->returnValue); 

        return $this->returnValue;
    }

    /* -------------------------------------------------------------------------- */
    /*                                    Roll                                    */
    /* -------------------------------------------------------------------------- */
    public function roll($from = 1, $to = 100) {
        return mt_rand($from, $to);
    }

    /* -------------------------------------------------------------------------- */
    /*                                 Percentage                                 */
    /* -------------------------------------------------------------------------- */
    public function percentage($chance = 50) {
        return mt_rand(0,100) <= $chance;
    }
}

?>